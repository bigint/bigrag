# User Authentication & Teams for bigRAG Admin UI

**Date:** 2026-03-29
**Status:** Approved

## Overview

Add username/password authentication, invite-based user management, and role-based access to the bigRAG admin UI. The first user to access the instance creates the admin account (setup flow). After that, admins invite users via shareable one-time links. All auth logic lives in the Rust backend; the Next.js frontend is a static client that stores a session token and sends it as a Bearer token.

## Requirements

- Initial admin account creation when no users exist (setup flow)
- Email/password login
- Invite-based signup (admin generates a link, shares it out-of-band)
- Two roles: Admin and Member
  - Admin: full access, manage users, manage invites, create any API key
  - Member: read/write namespaces, create API keys scoped to own permissions (`admin: false`)
- API keys persist in Postgres (replacing in-memory store)
- Master key remains as emergency bypass
- No SMTP dependency, no OAuth, no external auth service

## Data Model (Postgres via sqlx)

### `users`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, default gen_random_uuid() |
| email | VARCHAR(255) | Unique, used for login |
| password_hash | VARCHAR(255) | argon2id |
| display_name | VARCHAR(128) | |
| role | VARCHAR(20) | `admin` or `member` |
| created_at | TIMESTAMPTZ | default now() |
| updated_at | TIMESTAMPTZ | default now() |

### `sessions`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, default gen_random_uuid() |
| user_id | UUID | FK -> users ON DELETE CASCADE |
| token_hash | VARCHAR(255) | SHA-256 of session token |
| expires_at | TIMESTAMPTZ | 7-day rolling expiry |
| created_at | TIMESTAMPTZ | default now() |

### `invites`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, default gen_random_uuid() |
| code | VARCHAR(64) | Unique, URL-safe random string |
| role | VARCHAR(20) | Role assigned on signup |
| created_by | UUID | FK -> users |
| used_by | UUID | FK -> users, NULL until used |
| expires_at | TIMESTAMPTZ | default 7 days from creation |
| created_at | TIMESTAMPTZ | default now() |

### `api_keys`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, default gen_random_uuid() |
| user_id | UUID | FK -> users ON DELETE CASCADE |
| name | VARCHAR(128) | |
| key_hash | VARCHAR(255) | SHA-256 |
| prefix | VARCHAR(10) | First 8 chars for display |
| permissions | JSONB | `{namespaces, operations, admin}` |
| expires_at | TIMESTAMPTZ | Optional |
| created_at | TIMESTAMPTZ | default now() |
| last_used_at | TIMESTAMPTZ | |

## Backend API Endpoints

### Public (no auth required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/auth/setup-status` | Returns `{needs_setup: bool}` — true when zero users exist |
| POST | `/v1/auth/setup` | Create initial admin. Only works when zero users. Body: `{email, password, display_name}`. Returns `{token, user}` |
| POST | `/v1/auth/login` | Body: `{email, password}`. Returns `{token, user}` |
| POST | `/v1/auth/signup` | Body: `{email, password, display_name, invite_code}`. Returns `{token, user}` |

### Protected (session token required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/auth/me` | Current user profile |
| POST | `/v1/auth/logout` | Invalidate current session |
| PUT | `/v1/auth/password` | Change own password. Body: `{current_password, new_password}` |

### Admin-only

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/users` | List all users |
| DELETE | `/v1/admin/users/{id}` | Remove user (cascades: sessions + API keys) |
| PATCH | `/v1/admin/users/{id}` | Update user role. Body: `{role}` |
| POST | `/v1/admin/invites` | Create invite. Body: `{role, expires_in_hours?}`. Returns `{id, code, url, role, expires_at}` |
| GET | `/v1/admin/invites` | List invites (pending + used) |
| DELETE | `/v1/admin/invites/{id}` | Revoke invite |

### Existing endpoints (modified)

`POST /v1/admin/api-keys` — now associates key with authenticated user. Members can call it; their keys are forced to `admin: false`. Admins can set any permissions.

`GET /v1/admin/api-keys` — admins see all keys, members see only their own.

`DELETE /v1/admin/api-keys/{id}` — admins can revoke any key, members only their own.

## Auth Middleware Changes

Token validation order in `auth_middleware`:

1. **Master key** — plaintext comparison (unchanged)
2. **Session token** — query `sessions` table by token hash, check expiry, load user, synthesize `ApiKey` permissions from role:
   - Admin: all operations, `admin: true`, namespace `*`
   - Member: Read/Write/Delete/Schema, `admin: false`, namespace `*`
3. **API key** — query `api_keys` table by token hash (moved from in-memory to Postgres)
4. **JWT** — HS256 validation (unchanged, for external integrations)

Open mode remains: if no Postgres configured, no master key, and no JWT config, all requests are allowed (backward compatible for users who don't want auth).

## Rust Implementation

### New dependencies

- `sqlx` — Postgres async driver with migrations
- `argon2` — password hashing (argon2id)

### File structure

```
crates/bigrag-api/
  migrations/
    001_create_auth_tables.sql
  src/
    auth/
      mod.rs          # module root, re-exports
      password.rs     # argon2id hash + verify
      session.rs      # create/validate/revoke, 32-byte token gen
      handlers.rs     # setup, login, signup, logout, me, password change
      admin.rs        # user CRUD, invite CRUD
    db.rs             # PgPool init, run migrations on startup
```

### CLI / env changes

- `--database-url` / `BIGRAG_DATABASE_URL` — Postgres connection string. Optional; if not provided, auth is disabled and the system runs in open mode (backward compatible).
- Master key and API key CLI args remain unchanged.

### Startup flow

1. If `database_url` is provided: connect to Postgres, run pending migrations via `sqlx::migrate!()`, initialize auth tables.
2. Check if `users` table is empty -> set `needs_setup = true` in app state.
3. If `database_url` is not provided: auth disabled, in-memory API key store used as before (master key + `--api-keys` CLI args). No user/session/invite functionality available.
4. Start server.

## Frontend Changes

### Auth store (`lib/auth-store.ts`)

Add:
- `getSessionToken()` / `setSessionToken(token)` — localStorage key: `bigrag_session_token`
- `getUser()` / `setUser(user)` / `clearUser()` — localStorage key: `bigrag_user`
- `clearAuth()` — clears session token + user + legacy API key

The session token is sent as `Authorization: Bearer <token>` — same as the current API key flow. No changes to `api.ts` request headers logic.

### Auth guard

A client component wrapping the layout. On mount:
1. Check for session token in localStorage
2. If present, call `GET /v1/auth/me` to validate
3. If valid -> render children (sidebar + main content)
4. If no token or 401 -> redirect to `/login`

Special case: on initial load, first call `GET /v1/auth/setup-status`. If `needs_setup` is true, redirect to `/setup` instead of `/login`.

### New pages

| Route | Component | Description |
|-------|-----------|-------------|
| `/login` | Login form | Email + password. On success: store token + user, redirect to `/` |
| `/setup` | Setup form | Initial admin creation. Email + password + display name. Only accessible when `needs_setup` is true |
| `/signup` | Signup form | Reads `?code=xxx` from URL. Validates code, shows form. Email + password + display name |
| `/users` | Users page | Admin-only. List users, change roles, remove users. Invite section: create invite, copy link, list pending invites |

### Sidebar changes

- Show current user at the bottom (display name + role badge)
- Add "Users" nav item visible to admins only
- Add logout button

### 401 handling

In `api.ts`, if any request returns 401: call `clearAuth()` and `window.location.href = '/login'`.

## Security

- **Password hashing:** argon2id with default params from the `argon2` crate
- **Session tokens:** 32 random bytes, base64url encoded. Stored as SHA-256 hash in DB. Never stored in plaintext server-side.
- **Session expiry:** 7 days from creation, checked on every validation
- **Setup endpoint lockout:** `POST /v1/auth/setup` returns 403 if any user exists
- **Invite codes:** 32 random bytes, base64url encoded. Single-use, expire in 7 days by default
- **User deletion cascade:** FK ON DELETE CASCADE removes sessions and API keys
- **Master key:** Unchanged, bypasses all user auth
- **Backward compatibility:** If no `database_url` configured, system runs exactly as before (open mode or API key only)

## Out of Scope (future)

- Email/SMTP for invites
- OAuth/SSO
- Rate limiting on auth endpoints
- Per-user namespace scoping
- Audit logs
- Password reset flow (admin can delete and re-invite)
- Session refresh/rolling expiry
