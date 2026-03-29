# User Authentication & Teams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add username/password authentication, invite-based user management, and role-based access to bigRAG's admin UI and API.

**Architecture:** All auth logic lives in the Rust backend. Postgres stores users, sessions, invites, and API keys (replacing the in-memory API key store when DB is configured). The Next.js frontend is a static client that stores session tokens in localStorage and sends them as Bearer tokens. An auth guard component protects all routes except login/setup/signup.

**Tech Stack:** Rust (axum, sqlx, argon2), Postgres, Next.js (React 19, TanStack Query), localStorage

**Spec:** `docs/superpowers/specs/2026-03-29-user-auth-teams-design.md`

---

### Task 1: Add sqlx and argon2 dependencies to workspace

**Files:**
- Modify: `Cargo.toml` (workspace root)
- Modify: `crates/bigrag-api/Cargo.toml`
- Modify: `crates/bigrag-server/Cargo.toml`

- [ ] **Step 1: Add workspace dependencies**

In `Cargo.toml` (workspace root), add to `[workspace.dependencies]`:

```toml
sqlx = { version = "0.8", features = ["runtime-tokio", "tls-rustls", "postgres", "uuid", "chrono", "json", "migrate"] }
argon2 = "0.5"
```

- [ ] **Step 2: Add dependencies to bigrag-api**

In `crates/bigrag-api/Cargo.toml`, add to `[dependencies]`:

```toml
sqlx = { workspace = true }
argon2 = { workspace = true }
```

- [ ] **Step 3: Add sqlx to bigrag-server**

In `crates/bigrag-server/Cargo.toml`, add to `[dependencies]`:

```toml
sqlx = { workspace = true }
```

- [ ] **Step 4: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml Cargo.lock crates/bigrag-api/Cargo.toml crates/bigrag-server/Cargo.toml
git commit -m "feat: add sqlx and argon2 dependencies for user auth"
```

---

### Task 2: Create SQL migration for auth tables

**Files:**
- Create: `crates/bigrag-api/migrations/001_create_auth_tables.sql`

- [ ] **Step 1: Create the migration file**

Create `crates/bigrag-api/migrations/001_create_auth_tables.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_role CHECK (role IN ('admin', 'member'))
);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    created_by UUID NOT NULL REFERENCES users(id),
    used_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT valid_invite_role CHECK (role IN ('admin', 'member'))
);

CREATE INDEX idx_invites_code ON invites(code);

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    prefix VARCHAR(10) NOT NULL,
    permissions JSONB NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
```

- [ ] **Step 2: Commit**

```bash
git add crates/bigrag-api/migrations/
git commit -m "feat: add SQL migration for auth tables"
```

---

### Task 3: Add database connection module

**Files:**
- Create: `crates/bigrag-api/src/db.rs`
- Modify: `crates/bigrag-api/src/lib.rs` (add `pub mod db;`)

- [ ] **Step 1: Create db.rs**

Create `crates/bigrag-api/src/db.rs`:

```rust
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use tracing::info;

/// Initialize a Postgres connection pool and run pending migrations.
pub async fn init_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    let pool = PgPoolOptions::new()
        .max_connections(10)
        .connect(database_url)
        .await?;

    info!("connected to Postgres, running migrations");
    sqlx::migrate!("./migrations").run(&pool).await?;
    info!("migrations complete");

    Ok(pool)
}
```

- [ ] **Step 2: Add module declaration**

In `crates/bigrag-api/src/lib.rs`, add:

```rust
pub mod db;
```

- [ ] **Step 3: Verify it compiles**

Run: `cargo check`
Expected: Compiles. (The `sqlx::migrate!` macro reads `crates/bigrag-api/migrations/` at compile time.)

- [ ] **Step 4: Commit**

```bash
git add crates/bigrag-api/src/db.rs crates/bigrag-api/src/lib.rs
git commit -m "feat: add database connection and migration module"
```

---

### Task 4: Implement password hashing module

**Files:**
- Create: `crates/bigrag-api/src/auth/mod.rs`
- Create: `crates/bigrag-api/src/auth/password.rs`
- Modify: `crates/bigrag-api/src/lib.rs` (add `pub mod auth;`)

- [ ] **Step 1: Create auth module root**

Create `crates/bigrag-api/src/auth/mod.rs`:

```rust
pub mod password;
pub mod session;
pub mod handlers;
pub mod admin;
```

Note: `session`, `handlers`, and `admin` modules will be created in later tasks. For now, comment them out or allow dead code. Actually, just declare them all now — the compiler will error on missing files. Instead, create stubs:

Create `crates/bigrag-api/src/auth/session.rs`:
```rust
// Implemented in Task 5
```

Create `crates/bigrag-api/src/auth/handlers.rs`:
```rust
// Implemented in Task 6
```

Create `crates/bigrag-api/src/auth/admin.rs`:
```rust
// Implemented in Task 7
```

- [ ] **Step 2: Implement password.rs**

Create `crates/bigrag-api/src/auth/password.rs`:

```rust
use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};

/// Hash a plaintext password with argon2id. Returns the PHC string.
pub fn hash_password(password: &str) -> Result<String, argon2::password_hash::Error> {
    let salt = SaltString::generate(&mut OsRng);
    let argon2 = Argon2::default();
    let hash = argon2.hash_password(password.as_bytes(), &salt)?;
    Ok(hash.to_string())
}

/// Verify a plaintext password against a stored PHC hash string.
pub fn verify_password(password: &str, hash: &str) -> bool {
    let Ok(parsed) = PasswordHash::new(hash) else {
        return false;
    };
    Argon2::default()
        .verify_password(password.as_bytes(), &parsed)
        .is_ok()
}
```

- [ ] **Step 3: Add module to lib.rs**

In `crates/bigrag-api/src/lib.rs`, add:

```rust
pub mod auth;
```

- [ ] **Step 4: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 5: Commit**

```bash
git add crates/bigrag-api/src/auth/
git commit -m "feat: add password hashing module with argon2id"
```

---

### Task 5: Implement session management module

**Files:**
- Modify: `crates/bigrag-api/src/auth/session.rs`

- [ ] **Step 1: Implement session.rs**

Replace the stub in `crates/bigrag-api/src/auth/session.rs`:

```rust
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{Duration, Utc};
use rand::RngCore;
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use uuid::Uuid;

/// Generate a cryptographically random session token (base64url, 32 bytes).
pub fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    URL_SAFE_NO_PAD.encode(bytes)
}

/// SHA-256 hash a token for storage. Returns hex string.
pub fn hash_token(token: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(token.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// User row from the database.
#[derive(Debug, Clone, serde::Serialize)]
pub struct User {
    pub id: Uuid,
    pub email: String,
    pub display_name: String,
    pub role: String,
    pub created_at: chrono::DateTime<Utc>,
    pub updated_at: chrono::DateTime<Utc>,
}

/// Internal user row including password hash (never serialized to clients).
#[derive(Debug)]
pub struct UserRow {
    pub id: Uuid,
    pub email: String,
    pub password_hash: String,
    pub display_name: String,
    pub role: String,
    pub created_at: chrono::DateTime<Utc>,
    pub updated_at: chrono::DateTime<Utc>,
}

/// Create a new session for a user. Returns the plaintext token.
pub async fn create_session(pool: &PgPool, user_id: Uuid) -> Result<String, sqlx::Error> {
    let token = generate_token();
    let token_hash = hash_token(&token);
    let expires_at = Utc::now() + Duration::days(7);

    sqlx::query(
        "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
    )
    .bind(user_id)
    .bind(&token_hash)
    .bind(expires_at)
    .execute(pool)
    .await?;

    Ok(token)
}

/// Validate a session token. Returns the user if valid and not expired.
pub async fn validate_session(pool: &PgPool, token: &str) -> Result<Option<User>, sqlx::Error> {
    let token_hash = hash_token(token);

    let row = sqlx::query_as!(
        User,
        r#"
        SELECT u.id, u.email, u.display_name, u.role, u.created_at, u.updated_at
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token_hash = $1 AND s.expires_at > now()
        "#,
        &token_hash
    )
    .fetch_optional(pool)
    .await?;

    Ok(row)
}

/// Revoke a session by token hash.
pub async fn revoke_session(pool: &PgPool, token: &str) -> Result<(), sqlx::Error> {
    let token_hash = hash_token(token);
    sqlx::query("DELETE FROM sessions WHERE token_hash = $1")
        .bind(&token_hash)
        .execute(pool)
        .await?;
    Ok(())
}

/// Delete all expired sessions (cleanup).
pub async fn cleanup_expired_sessions(pool: &PgPool) -> Result<u64, sqlx::Error> {
    let result = sqlx::query("DELETE FROM sessions WHERE expires_at <= now()")
        .execute(pool)
        .await?;
    Ok(result.rows_affected())
}

/// Check if any users exist in the database.
pub async fn has_users(pool: &PgPool) -> Result<bool, sqlx::Error> {
    let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM users")
        .fetch_one(pool)
        .await?;
    Ok(row.0 > 0)
}

/// Find a user by email (with password hash for login verification).
pub async fn find_user_by_email(pool: &PgPool, email: &str) -> Result<Option<UserRow>, sqlx::Error> {
    let row = sqlx::query_as!(
        UserRow,
        "SELECT id, email, password_hash, display_name, role, created_at, updated_at FROM users WHERE email = $1",
        email
    )
    .fetch_optional(pool)
    .await?;
    Ok(row)
}

/// Create a new user. Returns the user (without password hash).
pub async fn create_user(
    pool: &PgPool,
    email: &str,
    password_hash: &str,
    display_name: &str,
    role: &str,
) -> Result<User, sqlx::Error> {
    let user = sqlx::query_as!(
        User,
        r#"
        INSERT INTO users (email, password_hash, display_name, role)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, display_name, role, created_at, updated_at
        "#,
        email,
        password_hash,
        display_name,
        role,
    )
    .fetch_one(pool)
    .await?;
    Ok(user)
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 3: Commit**

```bash
git add crates/bigrag-api/src/auth/session.rs
git commit -m "feat: add session management and user queries"
```

---

### Task 6: Implement auth endpoint handlers (setup, login, signup, me, logout, password)

**Files:**
- Modify: `crates/bigrag-api/src/auth/handlers.rs`

- [ ] **Step 1: Implement handlers.rs**

Replace the stub in `crates/bigrag-api/src/auth/handlers.rs`:

```rust
use axum::{
    extract::{Extension, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use sqlx::PgPool;
use tracing::{info, warn};

use super::password::{hash_password, verify_password};
use super::session::{
    create_session, create_user, find_user_by_email, has_users, revoke_session, User,
};
use crate::state::AppState;

// -- Request types --

#[derive(Debug, Deserialize)]
pub struct SetupRequest {
    pub email: String,
    pub password: String,
    pub display_name: String,
}

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Deserialize)]
pub struct SignupRequest {
    pub email: String,
    pub password: String,
    pub display_name: String,
    pub invite_code: String,
}

#[derive(Debug, Deserialize)]
pub struct ChangePasswordRequest {
    pub current_password: String,
    pub new_password: String,
}

// -- Helpers --

fn error_response(status: StatusCode, code: &str, message: &str) -> impl IntoResponse {
    (
        status,
        Json(serde_json::json!({
            "error": { "code": code, "message": message }
        })),
    )
}

fn validate_email(email: &str) -> bool {
    let trimmed = email.trim();
    !trimmed.is_empty() && trimmed.contains('@') && trimmed.len() <= 255
}

fn validate_password(password: &str) -> bool {
    password.len() >= 8 && password.len() <= 128
}

// -- Handlers --

/// GET /v1/auth/setup-status
pub async fn setup_status(State(state): State<AppState>) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match has_users(pool).await {
        Ok(has) => (
            StatusCode::OK,
            Json(serde_json::json!({ "needs_setup": !has })),
        )
            .into_response(),
        Err(e) => {
            warn!("setup_status: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to check setup status",
            )
            .into_response()
        }
    }
}

/// POST /v1/auth/setup — Create initial admin account.
pub async fn setup(
    State(state): State<AppState>,
    Json(body): Json<SetupRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    // Only works when no users exist
    match has_users(pool).await {
        Ok(true) => {
            return error_response(
                StatusCode::FORBIDDEN,
                "FORBIDDEN",
                "Setup already completed",
            )
            .into_response();
        }
        Err(e) => {
            warn!("setup: db error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Database error",
            )
            .into_response();
        }
        Ok(false) => {}
    }

    if !validate_email(&body.email) {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Invalid email")
            .into_response();
    }
    if !validate_password(&body.password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Password must be 8-128 characters",
        )
        .into_response();
    }
    if body.display_name.trim().is_empty() || body.display_name.len() > 128 {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Display name must be 1-128 characters",
        )
        .into_response();
    }

    let pw_hash = match hash_password(&body.password) {
        Ok(h) => h,
        Err(e) => {
            warn!("setup: password hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    let user = match create_user(pool, &body.email, &pw_hash, &body.display_name, "admin").await {
        Ok(u) => u,
        Err(e) => {
            warn!("setup: create user error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create user",
            )
            .into_response();
        }
    };

    let token = match create_session(pool, user.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("setup: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    info!(user_id = %user.id, email = %user.email, "initial admin account created");

    (
        StatusCode::CREATED,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// POST /v1/auth/login
pub async fn login(
    State(state): State<AppState>,
    Json(body): Json<LoginRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    let user_row = match find_user_by_email(pool, &body.email).await {
        Ok(Some(u)) => u,
        Ok(None) => {
            return error_response(
                StatusCode::UNAUTHORIZED,
                "UNAUTHORIZED",
                "Invalid email or password",
            )
            .into_response();
        }
        Err(e) => {
            warn!("login: db error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Database error",
            )
            .into_response();
        }
    };

    if !verify_password(&body.password, &user_row.password_hash) {
        return error_response(
            StatusCode::UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password",
        )
        .into_response();
    }

    let token = match create_session(pool, user_row.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("login: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    let user = User {
        id: user_row.id,
        email: user_row.email,
        display_name: user_row.display_name,
        role: user_row.role,
        created_at: user_row.created_at,
        updated_at: user_row.updated_at,
    };

    info!(user_id = %user.id, "user logged in");

    (
        StatusCode::OK,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// POST /v1/auth/signup — Invite-based signup.
pub async fn signup(
    State(state): State<AppState>,
    Json(body): Json<SignupRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    if !validate_email(&body.email) {
        return error_response(StatusCode::BAD_REQUEST, "BAD_REQUEST", "Invalid email")
            .into_response();
    }
    if !validate_password(&body.password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Password must be 8-128 characters",
        )
        .into_response();
    }
    if body.display_name.trim().is_empty() || body.display_name.len() > 128 {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Display name must be 1-128 characters",
        )
        .into_response();
    }

    // Validate invite code
    let invite = match sqlx::query_as!(
        InviteRow,
        "SELECT id, code, role, used_by, expires_at FROM invites WHERE code = $1",
        &body.invite_code,
    )
    .fetch_optional(pool)
    .await
    {
        Ok(Some(inv)) => inv,
        Ok(None) => {
            return error_response(
                StatusCode::BAD_REQUEST,
                "INVALID_INVITE",
                "Invalid invite code",
            )
            .into_response();
        }
        Err(e) => {
            warn!("signup: db error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Database error",
            )
            .into_response();
        }
    };

    if invite.used_by.is_some() {
        return error_response(
            StatusCode::BAD_REQUEST,
            "INVITE_USED",
            "Invite code already used",
        )
        .into_response();
    }

    if invite.expires_at < chrono::Utc::now() {
        return error_response(
            StatusCode::BAD_REQUEST,
            "INVITE_EXPIRED",
            "Invite code has expired",
        )
        .into_response();
    }

    let pw_hash = match hash_password(&body.password) {
        Ok(h) => h,
        Err(e) => {
            warn!("signup: password hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    let user = match create_user(pool, &body.email, &pw_hash, &body.display_name, &invite.role).await {
        Ok(u) => u,
        Err(e) if e.to_string().contains("duplicate key") => {
            return error_response(
                StatusCode::CONFLICT,
                "EMAIL_TAKEN",
                "Email already registered",
            )
            .into_response();
        }
        Err(e) => {
            warn!("signup: create user error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create user",
            )
            .into_response();
        }
    };

    // Mark invite as used
    let _ = sqlx::query("UPDATE invites SET used_by = $1 WHERE id = $2")
        .bind(user.id)
        .bind(invite.id)
        .execute(pool)
        .await;

    let token = match create_session(pool, user.id).await {
        Ok(t) => t,
        Err(e) => {
            warn!("signup: create session error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create session",
            )
            .into_response();
        }
    };

    info!(user_id = %user.id, email = %user.email, "user signed up via invite");

    (
        StatusCode::CREATED,
        Json(serde_json::json!({ "token": token, "user": user })),
    )
        .into_response()
}

/// GET /v1/auth/me — Current user profile.
pub async fn me(user: Extension<SessionUser>) -> impl IntoResponse {
    (StatusCode::OK, Json(serde_json::json!({ "user": user.0 }))).into_response()
}

/// POST /v1/auth/logout — Invalidate current session.
pub async fn logout(
    State(state): State<AppState>,
    Extension(token): Extension<SessionToken>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    let _ = revoke_session(pool, &token.0).await;
    (
        StatusCode::OK,
        Json(serde_json::json!({ "status": "ok" })),
    )
        .into_response()
}

/// PUT /v1/auth/password — Change own password.
pub async fn change_password(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Json(body): Json<ChangePasswordRequest>,
) -> impl IntoResponse {
    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    if !validate_password(&body.new_password) {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "New password must be 8-128 characters",
        )
        .into_response();
    }

    // Verify current password
    let user_row = match find_user_by_email(pool, &user.email).await {
        Ok(Some(u)) => u,
        _ => {
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to verify current password",
            )
            .into_response();
        }
    };

    if !verify_password(&body.current_password, &user_row.password_hash) {
        return error_response(
            StatusCode::UNAUTHORIZED,
            "UNAUTHORIZED",
            "Current password is incorrect",
        )
        .into_response();
    }

    let new_hash = match hash_password(&body.new_password) {
        Ok(h) => h,
        Err(e) => {
            warn!("change_password: hash error: {e}");
            return error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to hash password",
            )
            .into_response();
        }
    };

    match sqlx::query("UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2")
        .bind(&new_hash)
        .bind(user.id)
        .execute(pool)
        .await
    {
        Ok(_) => {
            info!(user_id = %user.id, "password changed");
            (
                StatusCode::OK,
                Json(serde_json::json!({ "status": "ok" })),
            )
                .into_response()
        }
        Err(e) => {
            warn!("change_password: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to update password",
            )
            .into_response()
        }
    }
}

// -- Supporting types used as request extensions --

/// Inserted by auth middleware when a session token is validated.
#[derive(Debug, Clone, serde::Serialize)]
pub struct SessionUser(pub User);

impl std::ops::Deref for SessionUser {
    type Target = User;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

/// Inserted by auth middleware — the raw session token for logout.
#[derive(Debug, Clone)]
pub struct SessionToken(pub String);

/// Invite row from the database (internal).
#[derive(Debug)]
struct InviteRow {
    id: uuid::Uuid,
    #[allow(dead_code)]
    code: String,
    role: String,
    used_by: Option<uuid::Uuid>,
    expires_at: chrono::DateTime<chrono::Utc>,
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cargo check`
Expected: Compiles (some unused warnings are OK — handlers aren't wired into routes yet).

- [ ] **Step 3: Commit**

```bash
git add crates/bigrag-api/src/auth/handlers.rs
git commit -m "feat: add auth handlers for setup, login, signup, me, logout, password"
```

---

### Task 7: Implement admin handlers (users + invites)

**Files:**
- Modify: `crates/bigrag-api/src/auth/admin.rs`

- [ ] **Step 1: Implement admin.rs**

Replace the stub in `crates/bigrag-api/src/auth/admin.rs`:

```rust
use axum::{
    extract::{Extension, Path, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{Duration, Utc};
use rand::RngCore;
use serde::Deserialize;
use tracing::{info, warn};
use uuid::Uuid;

use super::handlers::{error_response, SessionUser};
use super::session::User;
use crate::state::AppState;

// -- Request types --

#[derive(Debug, Deserialize)]
pub struct CreateInviteRequest {
    #[serde(default = "default_role")]
    pub role: String,
    pub expires_in_hours: Option<i64>,
}

fn default_role() -> String {
    "member".to_string()
}

#[derive(Debug, Deserialize)]
pub struct UpdateUserRequest {
    pub role: String,
}

// -- Helpers --

fn generate_invite_code() -> String {
    let mut bytes = [0u8; 32];
    rand::rng().fill_bytes(&mut bytes);
    URL_SAFE_NO_PAD.encode(bytes)
}

fn require_admin_user(user: &SessionUser) -> Result<(), impl IntoResponse> {
    if user.role != "admin" {
        return Err(error_response(
            StatusCode::FORBIDDEN,
            "FORBIDDEN",
            "Admin permissions required",
        ));
    }
    Ok(())
}

// -- Handlers --

/// GET /v1/admin/users — List all users.
pub async fn list_users(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match sqlx::query_as!(
        User,
        "SELECT id, email, display_name, role, created_at, updated_at FROM users ORDER BY created_at"
    )
    .fetch_all(pool)
    .await
    {
        Ok(users) => (StatusCode::OK, Json(serde_json::json!({ "users": users }))).into_response(),
        Err(e) => {
            warn!("list_users: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to list users",
            )
            .into_response()
        }
    }
}

/// DELETE /v1/admin/users/{id} — Remove a user.
pub async fn delete_user(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    if user.id == id {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Cannot delete your own account",
        )
        .into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(id)
        .execute(pool)
        .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            info!(user_id = %id, "user deleted by admin {}", user.id);
            (
                StatusCode::OK,
                Json(serde_json::json!({ "status": "ok", "message": "User deleted" })),
            )
                .into_response()
        }
        Ok(_) => error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "User not found")
            .into_response(),
        Err(e) => {
            warn!("delete_user: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to delete user",
            )
            .into_response()
        }
    }
}

/// PATCH /v1/admin/users/{id} — Update user role.
pub async fn update_user(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
    Json(body): Json<UpdateUserRequest>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    if body.role != "admin" && body.role != "member" {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Role must be 'admin' or 'member'",
        )
        .into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match sqlx::query("UPDATE users SET role = $1, updated_at = now() WHERE id = $2")
        .bind(&body.role)
        .bind(id)
        .execute(pool)
        .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            info!(user_id = %id, new_role = %body.role, "user role updated by admin {}", user.id);
            (
                StatusCode::OK,
                Json(serde_json::json!({ "status": "ok" })),
            )
                .into_response()
        }
        Ok(_) => error_response(StatusCode::NOT_FOUND, "NOT_FOUND", "User not found")
            .into_response(),
        Err(e) => {
            warn!("update_user: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to update user",
            )
            .into_response()
        }
    }
}

/// POST /v1/admin/invites — Create an invite.
pub async fn create_invite(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Json(body): Json<CreateInviteRequest>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    if body.role != "admin" && body.role != "member" {
        return error_response(
            StatusCode::BAD_REQUEST,
            "BAD_REQUEST",
            "Role must be 'admin' or 'member'",
        )
        .into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    let code = generate_invite_code();
    let hours = body.expires_in_hours.unwrap_or(168); // 7 days default
    let expires_at = Utc::now() + Duration::hours(hours);

    match sqlx::query_as!(
        InviteResponse,
        r#"
        INSERT INTO invites (code, role, created_by, expires_at)
        VALUES ($1, $2, $3, $4)
        RETURNING id, code, role, expires_at, created_at
        "#,
        &code,
        &body.role,
        user.id,
        expires_at,
    )
    .fetch_one(pool)
    .await
    {
        Ok(invite) => {
            info!(invite_id = %invite.id, role = %invite.role, "invite created by {}", user.id);
            (StatusCode::CREATED, Json(serde_json::json!(invite))).into_response()
        }
        Err(e) => {
            warn!("create_invite: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to create invite",
            )
            .into_response()
        }
    }
}

/// GET /v1/admin/invites — List all invites.
pub async fn list_invites(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match sqlx::query_as!(
        InviteListItem,
        r#"
        SELECT i.id, i.code, i.role, i.expires_at, i.created_at, i.used_by,
               u.email as "created_by_email!"
        FROM invites i
        JOIN users u ON i.created_by = u.id
        ORDER BY i.created_at DESC
        "#,
    )
    .fetch_all(pool)
    .await
    {
        Ok(invites) => {
            (StatusCode::OK, Json(serde_json::json!({ "invites": invites }))).into_response()
        }
        Err(e) => {
            warn!("list_invites: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to list invites",
            )
            .into_response()
        }
    }
}

/// DELETE /v1/admin/invites/{id} — Revoke an invite.
pub async fn delete_invite(
    State(state): State<AppState>,
    Extension(user): Extension<SessionUser>,
    Path(id): Path<Uuid>,
) -> impl IntoResponse {
    if let Err(resp) = require_admin_user(&user) {
        return resp.into_response();
    }

    let Some(ref pool) = state.db_pool else {
        return error_response(
            StatusCode::SERVICE_UNAVAILABLE,
            "NO_DATABASE",
            "Database not configured",
        )
        .into_response();
    };

    match sqlx::query("DELETE FROM invites WHERE id = $1 AND used_by IS NULL")
        .bind(id)
        .execute(pool)
        .await
    {
        Ok(result) if result.rows_affected() > 0 => {
            info!(invite_id = %id, "invite revoked by {}", user.id);
            (
                StatusCode::OK,
                Json(serde_json::json!({ "status": "ok", "message": "Invite revoked" })),
            )
                .into_response()
        }
        Ok(_) => error_response(
            StatusCode::NOT_FOUND,
            "NOT_FOUND",
            "Invite not found or already used",
        )
        .into_response(),
        Err(e) => {
            warn!("delete_invite: db error: {e}");
            error_response(
                StatusCode::INTERNAL_SERVER_ERROR,
                "INTERNAL_ERROR",
                "Failed to revoke invite",
            )
            .into_response()
        }
    }
}

// -- Supporting types --

#[derive(Debug, serde::Serialize)]
struct InviteResponse {
    id: Uuid,
    code: String,
    role: String,
    expires_at: chrono::DateTime<Utc>,
    created_at: chrono::DateTime<Utc>,
}

#[derive(Debug, serde::Serialize)]
struct InviteListItem {
    id: Uuid,
    code: String,
    role: String,
    expires_at: chrono::DateTime<Utc>,
    created_at: chrono::DateTime<Utc>,
    used_by: Option<Uuid>,
    created_by_email: String,
}
```

- [ ] **Step 2: Make error_response public**

In `crates/bigrag-api/src/auth/handlers.rs`, change `fn error_response` to `pub fn error_response` so `admin.rs` can import it.

- [ ] **Step 3: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 4: Commit**

```bash
git add crates/bigrag-api/src/auth/admin.rs crates/bigrag-api/src/auth/handlers.rs
git commit -m "feat: add admin handlers for user and invite management"
```

---

### Task 8: Update AppState and auth middleware for session + Postgres API keys

**Files:**
- Modify: `crates/bigrag-api/src/state.rs`
- Modify: `crates/bigrag-api/src/middleware.rs`

- [ ] **Step 1: Add db_pool to AppState**

In `crates/bigrag-api/src/state.rs`, add to the `AppState` struct:

```rust
/// Optional Postgres pool for user auth. None = legacy mode.
pub db_pool: Option<PgPool>,
```

Add the import at the top:

```rust
use sqlx::PgPool;
```

Update `AppState::new` to accept and store `db_pool: Option<PgPool>`:

```rust
pub fn new(
    engine: Arc<StorageEngine>,
    key_store: ApiKeyStore,
    jwt_config: Option<JwtConfig>,
    prometheus_handle: PrometheusHandle,
    db_pool: Option<PgPool>,
) -> Self {
    Self {
        engine,
        documents: Arc::new(DashMap::new()),
        key_store: Arc::new(key_store),
        jwt_config: jwt_config.map(Arc::new),
        prometheus_handle,
        db_pool,
    }
}
```

- [ ] **Step 2: Update validate_auth to check sessions and Postgres API keys**

In `crates/bigrag-api/src/state.rs`, update `validate_auth` to return `Option<(ApiKey, Option<String>)>` where the second value is the raw token (needed for logout). Actually, it's simpler to keep validate_auth returning `Option<ApiKey>` and handle session tokens in middleware. Instead, add a new method:

```rust
/// Validate a bearer token. Tries: master key → session → Postgres API key → in-memory API key → JWT.
/// Returns (ApiKey, raw_token_if_session).
pub async fn validate_auth_async(&self, token: &str) -> (Option<ApiKey>, bool) {
    // 1. Master key (sync, fast)
    if let Some(ref mk) = self.key_store.master_key_ref() {
        if token == mk {
            return (Some(ApiKey {
                id: "master".to_string(),
                name: "master-key".to_string(),
                key_hash: String::new(),
                prefix: "master".to_string(),
                permissions: ApiKeyPermissions {
                    namespaces: vec!["*".to_string()],
                    operations: vec![
                        ApiOperation::Read,
                        ApiOperation::Write,
                        ApiOperation::Delete,
                        ApiOperation::Schema,
                        ApiOperation::Admin,
                    ],
                    admin: true,
                },
                created_at: String::new(),
                last_used_at: None,
                expires_at: None,
            }), false);
        }
    }

    // 2. Session token (async, requires db)
    if let Some(ref pool) = self.db_pool {
        if let Ok(Some(user)) = crate::auth::session::validate_session(pool, token).await {
            let is_admin = user.role == "admin";
            let mut operations = vec![
                ApiOperation::Read,
                ApiOperation::Write,
                ApiOperation::Delete,
                ApiOperation::Schema,
            ];
            if is_admin {
                operations.push(ApiOperation::Admin);
            }
            return (Some(ApiKey {
                id: format!("session-{}", user.id),
                name: user.display_name.clone(),
                key_hash: String::new(),
                prefix: "session".to_string(),
                permissions: ApiKeyPermissions {
                    namespaces: vec!["*".to_string()],
                    operations,
                    admin: is_admin,
                },
                created_at: user.created_at.to_rfc3339(),
                last_used_at: None,
                expires_at: None,
            }), true);
        }

        // 3. Postgres API keys
        let token_hash = crate::auth::session::hash_token(token);
        if let Ok(Some(row)) = sqlx::query_as::<_, PgApiKeyRow>(
            "SELECT id, name, prefix, permissions, expires_at, created_at, last_used_at FROM api_keys WHERE key_hash = $1"
        )
        .bind(&token_hash)
        .fetch_optional(pool)
        .await
        {
            if let Some(ref exp) = row.expires_at {
                if *exp < chrono::Utc::now() {
                    return (None, false);
                }
            }
            // Update last_used_at
            let _ = sqlx::query("UPDATE api_keys SET last_used_at = now() WHERE id = $1")
                .bind(row.id)
                .execute(pool)
                .await;

            let perms: ApiKeyPermissions = serde_json::from_value(row.permissions.clone())
                .unwrap_or(ApiKeyPermissions {
                    namespaces: vec![],
                    operations: vec![],
                    admin: false,
                });
            return (Some(ApiKey {
                id: row.id.to_string(),
                name: row.name,
                key_hash: token_hash,
                prefix: row.prefix,
                permissions: perms,
                created_at: row.created_at.to_rfc3339(),
                last_used_at: row.last_used_at.map(|t| t.to_rfc3339()),
                expires_at: row.expires_at.map(|t| t.to_rfc3339()),
            }), false);
        }
    }

    // 4. In-memory API key store (legacy)
    if let Some(key) = self.key_store.validate(token) {
        return (Some(key), false);
    }

    // 5. JWT
    if token.starts_with("ey") {
        if let Some(ref jwt_config) = self.jwt_config {
            if let Ok(api_key) = jwt_config.validate_jwt(token) {
                return (Some(api_key), false);
            }
        }
    }

    (None, false)
}
```

Add a helper to `ApiKeyStore` to expose master key for comparison:

```rust
pub fn master_key_ref(&self) -> &Option<String> {
    &self.master_key
}
```

Add the `PgApiKeyRow` struct in `state.rs`:

```rust
#[derive(sqlx::FromRow)]
struct PgApiKeyRow {
    id: uuid::Uuid,
    name: String,
    prefix: String,
    permissions: serde_json::Value,
    expires_at: Option<chrono::DateTime<chrono::Utc>>,
    created_at: chrono::DateTime<chrono::Utc>,
    last_used_at: Option<chrono::DateTime<chrono::Utc>>,
}
```

- [ ] **Step 3: Update auth_middleware to use async validation and inject session extensions**

In `crates/bigrag-api/src/middleware.rs`, update `auth_middleware`:

```rust
use crate::auth::handlers::{SessionToken, SessionUser};
use crate::auth::session::{validate_session, User};

pub async fn auth_middleware(
    axum::extract::State(state): axum::extract::State<AppState>,
    mut request: Request,
    next: Next,
) -> Response {
    // Open mode: no keys, no jwt, no database
    if state.key_store.is_open() && state.jwt_config.is_none() && state.db_pool.is_none() {
        trace!("auth: open mode, allowing request");
        return next.run(request).await;
    }

    let token = extract_bearer_token(request.headers());

    match token {
        Some(ref t) => {
            let (api_key, is_session) = state.validate_auth_async(t).await;
            match api_key {
                Some(key) => {
                    debug!(key_id = %key.id, key_name = %key.name, "auth: request authenticated");

                    // If this is a session-based auth, inject the user + token for handlers
                    if is_session {
                        if let Some(ref pool) = state.db_pool {
                            if let Ok(Some(user)) = validate_session(pool, t).await {
                                request.extensions_mut().insert(SessionUser(user));
                                request.extensions_mut().insert(SessionToken(t.clone()));
                            }
                        }
                    }

                    request.extensions_mut().insert(key);
                    next.run(request).await
                }
                None => {
                    warn!("auth: invalid token");
                    (
                        StatusCode::UNAUTHORIZED,
                        Json(serde_json::json!({
                            "error": {
                                "code": "UNAUTHORIZED",
                                "message": "Invalid API key"
                            }
                        })),
                    )
                        .into_response()
                }
            }
        }
        None => {
            warn!("auth: missing Authorization header");
            (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing Authorization header"
                    }
                })),
            )
                .into_response()
        }
    }
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 5: Commit**

```bash
git add crates/bigrag-api/src/state.rs crates/bigrag-api/src/middleware.rs
git commit -m "feat: update auth middleware for session and Postgres API key validation"
```

---

### Task 9: Wire auth routes into the router and update server startup

**Files:**
- Modify: `crates/bigrag-api/src/routes.rs`
- Modify: `crates/bigrag-server/src/main.rs`

- [ ] **Step 1: Add auth routes to the router**

In `crates/bigrag-api/src/routes.rs`, add the public auth routes (no middleware) and protected auth routes:

```rust
use crate::auth;

pub fn create_router(state: AppState) -> Router {
    // Public auth routes (no auth middleware)
    let auth_public_routes = Router::new()
        .route("/v1/auth/setup-status", get(auth::handlers::setup_status))
        .route("/v1/auth/setup", post(auth::handlers::setup))
        .route("/v1/auth/login", post(auth::handlers::login))
        .route("/v1/auth/signup", post(auth::handlers::signup));

    // Protected auth routes (require session)
    let auth_protected_routes = Router::new()
        .route("/v1/auth/me", get(auth::handlers::me))
        .route("/v1/auth/logout", post(auth::handlers::logout))
        .route("/v1/auth/password", put(auth::handlers::change_password));

    // Admin user/invite management routes
    let admin_user_routes = Router::new()
        .route(
            "/v1/admin/users",
            get(auth::admin::list_users),
        )
        .route(
            "/v1/admin/users/{id}",
            delete(auth::admin::delete_user).patch(auth::admin::update_user),
        )
        .route(
            "/v1/admin/invites",
            post(auth::admin::create_invite).get(auth::admin::list_invites),
        )
        .route(
            "/v1/admin/invites/{id}",
            delete(auth::admin::delete_invite),
        );

    let api_routes = Router::new()
        // ... existing routes stay the same ...
        .merge(auth_protected_routes)
        .merge(admin_user_routes)
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ));

    Router::new()
        .route("/health", get(handlers::health_check))
        .route("/v1/health/ready", get(handlers::readiness_probe))
        .route("/v1/health/live", get(handlers::liveness_probe))
        .route("/v1/metrics", get(handlers::prometheus_metrics))
        .merge(auth_public_routes)
        .merge(api_routes)
        .layer(middleware::from_fn(request_tracking))
        .with_state(state)
}
```

Add `put` to the axum routing import:

```rust
use axum::{
    middleware,
    routing::{delete, get, post, put},
    Router,
};
```

- [ ] **Step 2: Add --database-url CLI arg and connect on startup**

In `crates/bigrag-server/src/main.rs`, add to the `Cli` struct:

```rust
/// Postgres database URL for user authentication (optional).
#[arg(long, env = "BIGRAG_DATABASE_URL")]
database_url: Option<String>,
```

In the main function, after parsing CLI and before building `AppState`, add:

```rust
// Connect to Postgres if configured
let db_pool = if let Some(ref url) = cli.database_url {
    match bigrag_api::db::init_pool(url).await {
        Ok(pool) => {
            info!("database connected, user auth enabled");
            Some(pool)
        }
        Err(e) => {
            eprintln!("failed to connect to database: {e}");
            std::process::exit(1);
        }
    }
} else {
    info!("no database configured, running in legacy auth mode");
    None
};
```

Update the `AppState::new` call to pass `db_pool`:

```rust
let state = AppState::new(engine, key_store, jwt_config, prometheus_handle, db_pool);
```

- [ ] **Step 3: Verify it compiles**

Run: `cargo check`
Expected: Compiles with no errors.

- [ ] **Step 4: Commit**

```bash
git add crates/bigrag-api/src/routes.rs crates/bigrag-server/src/main.rs
git commit -m "feat: wire auth routes and database connection into server"
```

---

### Task 10: Update frontend auth store and API client

**Files:**
- Modify: `ui/src/lib/auth-store.ts`
- Modify: `ui/src/lib/api.ts`

- [ ] **Step 1: Update auth-store.ts with session token and user storage**

Replace `ui/src/lib/auth-store.ts`:

```typescript
const STORAGE_KEY_URL = "bigrag_url";
const STORAGE_KEY_SESSION = "bigrag_session_token";
const STORAGE_KEY_USER = "bigrag_user";

const DEFAULT_URL = process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:8080";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "member";
  created_at: string;
  updated_at: string;
}

export function getBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_URL;
  return localStorage.getItem(STORAGE_KEY_URL) || DEFAULT_URL;
}

export function setBaseUrl(url: string): void {
  if (typeof window === "undefined") return;
  if (url) {
    localStorage.setItem(STORAGE_KEY_URL, url);
  } else {
    localStorage.removeItem(STORAGE_KEY_URL);
  }
}

export function getSessionToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY_SESSION) ?? "";
}

export function setSessionToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_SESSION, token);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(STORAGE_KEY_USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setUser(user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY_SESSION);
  localStorage.removeItem(STORAGE_KEY_USER);
}

export function isAuthenticated(): boolean {
  return !!getSessionToken();
}
```

- [ ] **Step 2: Update api.ts to use session token and add auth endpoints**

In `ui/src/lib/api.ts`, update the import and request function:

```typescript
import { clearAuth, getBaseUrl, getSessionToken } from "./auth-store";
```

Update the `request` function to use session token and handle 401:

```typescript
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getSessionToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {})
  };

  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    cache: "no-store",
    headers
  });

  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/v1/auth/")) {
      clearAuth();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body?.error?.message || res.statusText,
      body?.error?.code
    );
  }

  return res.json();
}
```

Add auth API functions at the end of the file:

```typescript
// Auth

export interface AuthResponse {
  token: string;
  user: {
    id: string;
    email: string;
    display_name: string;
    role: string;
    created_at: string;
    updated_at: string;
  };
}

export async function getSetupStatus() {
  return request<{ needs_setup: boolean }>("/v1/auth/setup-status");
}

export async function setupAdmin(body: { email: string; password: string; display_name: string }) {
  return request<AuthResponse>("/v1/auth/setup", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function login(body: { email: string; password: string }) {
  return request<AuthResponse>("/v1/auth/login", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function signup(body: { email: string; password: string; display_name: string; invite_code: string }) {
  return request<AuthResponse>("/v1/auth/signup", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function getMe() {
  return request<{ user: AuthResponse["user"] }>("/v1/auth/me");
}

export async function logout() {
  return request<{ status: string }>("/v1/auth/logout", { method: "POST" });
}

export async function changePassword(body: { current_password: string; new_password: string }) {
  return request<{ status: string }>("/v1/auth/password", {
    body: JSON.stringify(body),
    method: "PUT"
  });
}

// Admin - Users

export interface UserSummary {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
  updated_at: string;
}

export async function listUsers() {
  return request<{ users: UserSummary[] }>("/v1/admin/users");
}

export async function deleteUser(id: string) {
  return request<{ status: string; message: string }>(`/v1/admin/users/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function updateUserRole(id: string, role: string) {
  return request<{ status: string }>(`/v1/admin/users/${encodeURIComponent(id)}`, {
    body: JSON.stringify({ role }),
    method: "PATCH"
  });
}

// Admin - Invites

export interface InviteSummary {
  id: string;
  code: string;
  role: string;
  expires_at: string;
  created_at: string;
  used_by: string | null;
  created_by_email: string;
}

export async function createInvite(body: { role?: string; expires_in_hours?: number }) {
  return request<InviteSummary>("/v1/admin/invites", {
    body: JSON.stringify(body),
    method: "POST"
  });
}

export async function listInvites() {
  return request<{ invites: InviteSummary[] }>("/v1/admin/invites");
}

export async function deleteInvite(id: string) {
  return request<{ status: string; message: string }>(`/v1/admin/invites/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}
```

Also update `getMetrics` at the bottom to use session token:

```typescript
export async function getMetrics() {
  const token = getSessionToken();
  const res = await fetch(`${getBaseUrl()}/v1/metrics`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  return res.text();
}
```

- [ ] **Step 3: Verify it compiles**

Run: `cd ui && npx next build`
Expected: Builds with no type errors. (Some pages may warn about missing imports from the auth guard — that's fine, we add it next.)

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/auth-store.ts ui/src/lib/api.ts
git commit -m "feat: update auth store and API client for session-based auth"
```

---

### Task 11: Create auth guard component and update layout

**Files:**
- Create: `ui/src/components/auth-guard.tsx`
- Modify: `ui/src/app/layout.tsx`

- [ ] **Step 1: Create auth-guard.tsx**

Create `ui/src/components/auth-guard.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  clearAuth,
  getSessionToken,
  getUser,
  isAuthenticated,
  setSessionToken,
  setUser
} from "@/lib/auth-store";
import { getMe, getSetupStatus } from "@/lib/api";

const PUBLIC_PATHS = ["/login", "/setup", "/signup"];

export const AuthGuard = ({ children }: { readonly children: React.ReactNode }) => {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);
  const [authorized, setAuthorized] = useState(false);

  const check = useCallback(async () => {
    const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

    // Check if setup is needed
    try {
      const { needs_setup } = await getSetupStatus();
      if (needs_setup) {
        if (pathname !== "/setup") {
          router.replace("/setup");
          return;
        }
        setAuthorized(true);
        setChecked(true);
        return;
      }
    } catch {
      // If setup-status fails (no DB), allow through — legacy mode
      setAuthorized(true);
      setChecked(true);
      return;
    }

    if (isPublic) {
      // If already logged in and trying to access login/setup, redirect to home
      if (isAuthenticated() && pathname === "/login") {
        router.replace("/");
        return;
      }
      setAuthorized(true);
      setChecked(true);
      return;
    }

    // Protected route — validate session
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }

    try {
      const { user } = await getMe();
      setUser(user);
      setAuthorized(true);
    } catch {
      clearAuth();
      router.replace("/login");
    } finally {
      setChecked(true);
    }
  }, [pathname, router]);

  useEffect(() => {
    check();
  }, [check]);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="size-5 animate-spin rounded-full border-2 border-border border-t-text" />
      </div>
    );
  }

  if (!authorized) return null;

  return <>{children}</>;
};
```

- [ ] **Step 2: Update layout.tsx to use AuthGuard**

Modify `ui/src/app/layout.tsx` — wrap children with AuthGuard and conditionally show Sidebar:

```tsx
import { GeistMono } from "geist/font/mono";
import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { Providers } from "@/lib/query-client";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit"
});

export const metadata: Metadata = {
  description: "Admin dashboard for bigRAG vector database",
  icons: {
    icon: "/logo.svg"
  },
  title: "bigRAG Admin"
};

const RootLayout = ({ children }: { readonly children: React.ReactNode }) => {
  return (
    <html className={`${outfit.variable} ${GeistMono.variable}`} lang="en">
      <body className="antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
};

export default RootLayout;
```

- [ ] **Step 3: Create an app shell component that wraps authenticated pages**

Create `ui/src/components/app-shell.tsx`:

```tsx
"use client";

import { AuthGuard } from "./auth-guard";
import { Sidebar } from "./sidebar";

export const AppShell = ({ children }: { readonly children: React.ReactNode }) => (
  <AuthGuard>
    <Sidebar />
    <main className="ml-56 min-h-screen">
      <div className="px-8 py-6">{children}</div>
    </main>
  </AuthGuard>
);
```

- [ ] **Step 4: Create a layout for authenticated pages**

Create `ui/src/app/(dashboard)/layout.tsx`:

```tsx
import { AppShell } from "@/components/app-shell";

const DashboardLayout = ({ children }: { readonly children: React.ReactNode }) => (
  <AppShell>{children}</AppShell>
);

export default DashboardLayout;
```

- [ ] **Step 5: Move all existing pages into the (dashboard) route group**

Move these directories/files into `ui/src/app/(dashboard)/`:
- `page.tsx` (dashboard home)
- `vault/`
- `namespaces/`
- `metrics/`
- `api-keys/`
- `settings/`

Run:
```bash
cd ui/src/app
mkdir -p "(dashboard)"
mv page.tsx vault namespaces metrics api-keys settings "(dashboard)"/
```

- [ ] **Step 6: Verify the restructure works**

Run: `cd ui && npx next build`
Expected: Builds successfully. All existing routes still work — the `(dashboard)` route group is invisible in the URL.

- [ ] **Step 7: Commit**

```bash
git add ui/src/components/auth-guard.tsx ui/src/components/app-shell.tsx ui/src/app/
git commit -m "feat: add auth guard and restructure layout with route groups"
```

---

### Task 12: Create login, setup, and signup pages

**Files:**
- Create: `ui/src/app/login/page.tsx`
- Create: `ui/src/app/setup/page.tsx`
- Create: `ui/src/app/signup/page.tsx`

- [ ] **Step 1: Create login page**

Create `ui/src/app/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { setSessionToken, setUser } from "@/lib/auth-store";

const LoginPage = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { token, user } = await login({ email, password });
      setSessionToken(token);
      setUser(user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-text">bigRAG</h1>
          <p className="mt-1 text-sm text-text-muted">Sign in to your account</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="email">
              Email
            </label>
            <input
              autoComplete="email"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="email"
              onChange={(e) => setEmail(e.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="current-password"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="password"
              onChange={(e) => setPassword(e.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          <button
            className="w-full rounded-md bg-text py-2 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
```

- [ ] **Step 2: Create setup page**

Create `ui/src/app/setup/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setupAdmin } from "@/lib/api";
import { setSessionToken, setUser } from "@/lib/auth-store";

const SetupPage = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { token, user } = await setupAdmin({
        email,
        password,
        display_name: displayName
      });
      setSessionToken(token);
      setUser(user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-text">bigRAG</h1>
          <p className="mt-1 text-sm text-text-muted">Create your admin account</p>
          <p className="mt-1 text-xs text-text-dim">This is the initial setup for your instance</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="displayName">
              Name
            </label>
            <input
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="displayName"
              onChange={(e) => setDisplayName(e.target.value)}
              required
              type="text"
              value={displayName}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="email">
              Email
            </label>
            <input
              autoComplete="email"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="email"
              onChange={(e) => setEmail(e.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="new-password"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="password"
              minLength={8}
              onChange={(e) => setPassword(e.target.value)}
              required
              type="password"
              value={password}
            />
            <p className="mt-1 text-xs text-text-dim">Minimum 8 characters</p>
          </div>

          <button
            className="w-full rounded-md bg-text py-2 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "Creating account..." : "Create admin account"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default SetupPage;
```

- [ ] **Step 3: Create signup page**

Create `ui/src/app/signup/page.tsx`:

```tsx
"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { signup } from "@/lib/api";
import { setSessionToken, setUser } from "@/lib/auth-store";

const SignupForm = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code") ?? "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { token, user } = await signup({
        email,
        password,
        display_name: displayName,
        invite_code: code
      });
      setSessionToken(token);
      setUser(user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  if (!code) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-text">bigRAG</h1>
          <p className="mt-2 text-sm text-text-muted">
            You need an invite link to create an account.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-text">bigRAG</h1>
          <p className="mt-1 text-sm text-text-muted">Create your account</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="displayName">
              Name
            </label>
            <input
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="displayName"
              onChange={(e) => setDisplayName(e.target.value)}
              required
              type="text"
              value={displayName}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="email">
              Email
            </label>
            <input
              autoComplete="email"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="email"
              onChange={(e) => setEmail(e.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm text-text-muted" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="new-password"
              className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-text-muted"
              id="password"
              minLength={8}
              onChange={(e) => setPassword(e.target.value)}
              required
              type="password"
              value={password}
            />
            <p className="mt-1 text-xs text-text-dim">Minimum 8 characters</p>
          </div>

          <button
            className="w-full rounded-md bg-text py-2 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
            disabled={loading}
            type="submit"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-text-dim">
          Already have an account?{" "}
          <a className="text-text-muted hover:text-text" href="/login">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
};

const SignupPage = () => (
  <Suspense>
    <SignupForm />
  </Suspense>
);

export default SignupPage;
```

- [ ] **Step 4: Verify it compiles**

Run: `cd ui && npx next build`
Expected: Builds successfully.

- [ ] **Step 5: Commit**

```bash
git add ui/src/app/login/ ui/src/app/setup/ ui/src/app/signup/
git commit -m "feat: add login, setup, and signup pages"
```

---

### Task 13: Update sidebar with user info, logout, and admin nav

**Files:**
- Modify: `ui/src/components/sidebar.tsx`

- [ ] **Step 1: Update sidebar.tsx**

Replace `ui/src/components/sidebar.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  HardDrive,
  Database,
  BarChart3,
  KeyRound,
  Settings,
  Users,
  LogOut
} from "lucide-react";
import { clearAuth, getUser } from "@/lib/auth-store";
import { logout } from "@/lib/api";
import { Logo } from "./logo";

const NAV_ITEMS = [
  { href: "/", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/vault", icon: HardDrive, label: "Vault" },
  { href: "/namespaces", icon: Database, label: "Namespaces" },
  { href: "/metrics", icon: BarChart3, label: "Metrics" },
  { href: "/api-keys", icon: KeyRound, label: "API Keys" },
  { href: "/settings", icon: Settings, label: "Settings" }
];

const ADMIN_ITEMS = [
  { href: "/users", icon: Users, label: "Users" }
];

export const Sidebar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();
  const isAdmin = user?.role === "admin";

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore — clear locally regardless
    }
    clearAuth();
    router.replace("/login");
  };

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-56 flex-col border-r border-border bg-bg">
      {/* Header */}
      <div className="flex h-14 items-center gap-2 px-5">
        <Logo />
        <span className="text-base font-semibold tracking-tight text-text">bigRAG</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 px-3 py-2">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors ${
                isActive
                  ? "bg-bg-hover text-text"
                  : "text-text-muted hover:bg-bg-hover hover:text-text"
              }`}
              href={href}
              key={href}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </Link>
          );
        })}

        {isAdmin && (
          <>
            <div className="my-2 border-t border-border" />
            {ADMIN_ITEMS.map(({ href, icon: Icon, label }) => {
              const isActive = pathname.startsWith(href);
              return (
                <Link
                  className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors ${
                    isActive
                      ? "bg-bg-hover text-text"
                      : "text-text-muted hover:bg-bg-hover hover:text-text"
                  }`}
                  href={href}
                  key={href}
                >
                  <Icon className="size-4 shrink-0" />
                  {label}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* User footer */}
      {user && (
        <div className="border-t border-border px-3 py-3">
          <div className="flex items-center justify-between px-2.5">
            <div className="min-w-0">
              <p className="truncate text-[13px] font-medium text-text">{user.display_name}</p>
              <p className="text-[11px] text-text-dim">{user.role}</p>
            </div>
            <button
              className="rounded-md p-1.5 text-text-dim hover:bg-bg-hover hover:text-text"
              onClick={handleLogout}
              title="Sign out"
              type="button"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
};
```

- [ ] **Step 2: Verify it compiles**

Run: `cd ui && npx next build`
Expected: Builds successfully.

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/sidebar.tsx
git commit -m "feat: update sidebar with user info, logout, and admin nav"
```

---

### Task 14: Create users management page

**Files:**
- Create: `ui/src/app/(dashboard)/users/page.tsx`

- [ ] **Step 1: Create users page**

Create `ui/src/app/(dashboard)/users/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInvite,
  deleteInvite,
  deleteUser,
  listInvites,
  listUsers,
  updateUserRole
} from "@/lib/api";
import type { InviteSummary, UserSummary } from "@/lib/api";
import { getUser } from "@/lib/auth-store";

const UsersPage = () => {
  const queryClient = useQueryClient();
  const currentUser = getUser();
  const [inviteRole, setInviteRole] = useState("member");
  const [createdInvite, setCreatedInvite] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const usersQuery = useQuery({
    queryFn: listUsers,
    queryKey: ["users"]
  });

  const invitesQuery = useQuery({
    queryFn: listInvites,
    queryKey: ["invites"]
  });

  const createInviteMutation = useMutation({
    mutationFn: () => createInvite({ role: inviteRole }),
    onSuccess: (data) => {
      const url = `${window.location.origin}/signup?code=${data.code}`;
      setCreatedInvite(url);
      queryClient.invalidateQueries({ queryKey: ["invites"] });
    }
  });

  const deleteUserMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] })
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => updateUserRole(id, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] })
  });

  const deleteInviteMutation = useMutation({
    mutationFn: deleteInvite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invites"] })
  });

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const users: UserSummary[] = usersQuery.data?.users ?? [];
  const invites: InviteSummary[] = invitesQuery.data?.invites ?? [];
  const pendingInvites = invites.filter((i) => !i.used_by);

  return (
    <div className="text-text">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            Manage users and invitations
          </p>
        </div>

        {/* Invite section */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Invite
          </h2>
          <div className="rounded-lg border border-border bg-bg-card p-5">
            {createdInvite ? (
              <div className="space-y-3">
                <p className="text-sm text-text-muted">Share this link with the new user:</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 truncate rounded-md border border-border bg-bg px-3 py-2 font-mono text-xs text-text">
                    {createdInvite}
                  </code>
                  <button
                    className="shrink-0 rounded-md border border-border px-3 py-2 text-xs text-text-muted hover:bg-bg-hover"
                    onClick={() => handleCopy(createdInvite)}
                    type="button"
                  >
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <button
                  className="text-xs text-text-dim hover:text-text-muted"
                  onClick={() => setCreatedInvite(null)}
                  type="button"
                >
                  Create another
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <select
                  className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-text"
                  onChange={(e) => setInviteRole(e.target.value)}
                  value={inviteRole}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  className="rounded-md bg-text px-4 py-2 text-sm font-medium text-bg hover:opacity-90 disabled:opacity-50"
                  disabled={createInviteMutation.isPending}
                  onClick={() => createInviteMutation.mutate()}
                  type="button"
                >
                  {createInviteMutation.isPending ? "Creating..." : "Create invite link"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Users table */}
        <div className="mb-8">
          <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
            Members ({users.length})
          </h2>
          <div className="rounded-lg border border-border bg-bg-card">
            {usersQuery.isLoading ? (
              <div className="px-5 py-12 text-center text-sm text-text-dim">Loading...</div>
            ) : users.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-text-dim">No users</div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-text-muted">
                    <th className="px-5 py-3 font-medium">Name</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">Joined</th>
                    <th className="px-5 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td className="px-5 py-3 text-text">{u.display_name}</td>
                      <td className="px-5 py-3 font-mono text-xs text-text-muted">{u.email}</td>
                      <td className="px-5 py-3">
                        <select
                          className="rounded border border-border bg-bg px-2 py-1 text-xs text-text"
                          disabled={u.id === currentUser?.id}
                          onChange={(e) =>
                            updateRoleMutation.mutate({ id: u.id, role: e.target.value })
                          }
                          value={u.role}
                        >
                          <option value="admin">admin</option>
                          <option value="member">member</option>
                        </select>
                      </td>
                      <td className="px-5 py-3 text-xs text-text-dim">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {u.id !== currentUser?.id && (
                          <button
                            className="text-xs text-danger hover:text-danger/80"
                            onClick={() => {
                              if (confirm(`Remove ${u.display_name}?`)) {
                                deleteUserMutation.mutate(u.id);
                              }
                            }}
                            type="button"
                          >
                            Remove
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Pending invites */}
        {pendingInvites.length > 0 && (
          <div>
            <h2 className="mb-4 text-sm font-medium uppercase tracking-wider text-text-muted">
              Pending Invites ({pendingInvites.length})
            </h2>
            <div className="rounded-lg border border-border bg-bg-card">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-text-muted">
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">Created by</th>
                    <th className="px-5 py-3 font-medium">Expires</th>
                    <th className="px-5 py-3 font-medium" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {pendingInvites.map((inv) => (
                    <tr key={inv.id}>
                      <td className="px-5 py-3 text-text">{inv.role}</td>
                      <td className="px-5 py-3 font-mono text-xs text-text-muted">
                        {inv.created_by_email}
                      </td>
                      <td className="px-5 py-3 text-xs text-text-dim">
                        {new Date(inv.expires_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          className="text-xs text-danger hover:text-danger/80"
                          onClick={() => deleteInviteMutation.mutate(inv.id)}
                          type="button"
                        >
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UsersPage;
```

- [ ] **Step 2: Verify it compiles**

Run: `cd ui && npx next build`
Expected: Builds successfully.

- [ ] **Step 3: Commit**

```bash
git add ui/src/app/\(dashboard\)/users/
git commit -m "feat: add users management page with invites"
```

---

### Task 15: Update settings page to remove API key field

**Files:**
- Modify: `ui/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Simplify settings page**

The settings page no longer needs the API key input or URL input — those are handled by the auth system now. Remove the connection configuration form and keep it as a read-only status page showing the current user's connection info, server config, and about section.

Remove the `apiKey`, `showKey`, `saved` state, the `handleSave` callback, and the API Key input. Keep the URL as read-only display (from `getBaseUrl()`). Keep the connection status, server configuration, and about sections.

Remove the imports for `setApiKey`, `setBaseUrl`, and `getApiKey` from `auth-store`. Keep `getBaseUrl`.

- [ ] **Step 2: Verify it compiles**

Run: `cd ui && npx next build`
Expected: Builds successfully.

- [ ] **Step 3: Commit**

```bash
git add ui/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat: simplify settings page for session-based auth"
```

---

### Task 16: End-to-end smoke test

**Files:** None (testing only)

- [ ] **Step 1: Start Postgres**

Run:
```bash
docker run -d --name bigrag-pg -e POSTGRES_PASSWORD=bigrag -e POSTGRES_DB=bigrag -p 5432:5432 postgres:17
```

- [ ] **Step 2: Build and start the backend with database**

Run:
```bash
cargo run -- --database-url "postgres://postgres:bigrag@localhost:5432/bigrag"
```

Expected: Logs show "connected to Postgres, running migrations" and "migrations complete".

- [ ] **Step 3: Test setup flow**

Run:
```bash
# Check setup status
curl -s http://localhost:8080/v1/auth/setup-status | jq .
# Expected: {"needs_setup": true}

# Create admin
curl -s -X POST http://localhost:8080/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"testpass123","display_name":"Admin"}' | jq .
# Expected: {"token": "...", "user": {"id": "...", "email": "admin@test.com", ...}}

# Setup locked out now
curl -s -X POST http://localhost:8080/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin2@test.com","password":"testpass123","display_name":"Admin2"}' | jq .
# Expected: 403 "Setup already completed"
```

- [ ] **Step 4: Test login and protected endpoints**

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"testpass123"}' | jq -r .token)

# Get profile
curl -s http://localhost:8080/v1/auth/me -H "Authorization: Bearer $TOKEN" | jq .
# Expected: user object

# Create invite
curl -s -X POST http://localhost:8080/v1/admin/invites \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"member"}' | jq .
# Expected: invite with code
```

- [ ] **Step 5: Test invite signup**

```bash
# Get invite code from previous response
CODE=$(curl -s http://localhost:8080/v1/admin/invites -H "Authorization: Bearer $TOKEN" | jq -r '.invites[0].code')

# Signup with invite
curl -s -X POST http://localhost:8080/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"user@test.com\",\"password\":\"testpass123\",\"display_name\":\"User\",\"invite_code\":\"$CODE\"}" | jq .
# Expected: {"token": "...", "user": {"role": "member", ...}}
```

- [ ] **Step 6: Test frontend**

Start the Next.js dev server:
```bash
cd ui && npm run dev
```

Open `http://localhost:3000` — should redirect to `/setup` (if fresh DB) or `/login`.

- [ ] **Step 7: Commit any fixes**

If any issues were found and fixed during testing, commit them:
```bash
git add -A
git commit -m "fix: address issues found during auth smoke testing"
```

---

### Task 17: Update API key endpoints to use Postgres when available

**Files:**
- Modify: `crates/bigrag-api/src/handlers.rs`

- [ ] **Step 1: Update create_api_key handler**

When `state.db_pool` is `Some`, store the new key in Postgres with the calling user's ID. When `None`, fall back to the in-memory store.

In the `create_api_key` handler, after validating the request body:

```rust
// If database is configured, store in Postgres
if let Some(ref pool) = state.db_pool {
    // Get calling user ID from session
    let user_id = match api_key.as_ref() {
        Some(k) if k.id.starts_with("session-") => {
            k.id.strip_prefix("session-").and_then(|id| uuid::Uuid::parse_str(id).ok())
        }
        _ => None,
    };

    // Members cannot create admin keys
    let is_admin_caller = caller_key.as_ref().map_or(false, |k| k.permissions.admin);
    let key_admin = if is_admin_caller { body.admin } else { false };

    let permissions = ApiKeyPermissions {
        namespaces: body.namespaces,
        operations: body.operations,
        admin: key_admin,
    };

    let plaintext = crate::state::generate_api_key();
    let prefix = plaintext[..11].to_string();
    let key_hash = crate::auth::session::hash_token(&plaintext);

    let perms_json = serde_json::to_value(&permissions).unwrap();

    match sqlx::query_as!(
        PgKeyCreated,
        r#"
        INSERT INTO api_keys (user_id, name, key_hash, prefix, permissions, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6::timestamptz)
        RETURNING id, name, prefix, created_at, expires_at
        "#,
        user_id,
        &body.name,
        &key_hash,
        &prefix,
        &perms_json,
        body.expires_at.as_deref().map(|s| chrono::DateTime::parse_from_rfc3339(s).ok()).flatten(),
    )
    .fetch_one(pool)
    .await
    {
        Ok(row) => {
            return (
                StatusCode::CREATED,
                Json(serde_json::json!({
                    "key": plaintext,
                    "id": row.id,
                    "name": row.name,
                    "prefix": row.prefix,
                    "permissions": permissions,
                    "created_at": row.created_at,
                    "expires_at": row.expires_at,
                })),
            ).into_response();
        }
        Err(e) => {
            warn!("create_api_key: db error: {e}");
            return error_response(StatusCode::INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Failed to create API key").into_response();
        }
    }
}

// Fallback to in-memory store (legacy mode)
// ... existing code ...
```

Add the helper type:
```rust
struct PgKeyCreated {
    id: uuid::Uuid,
    name: String,
    prefix: String,
    created_at: chrono::DateTime<chrono::Utc>,
    expires_at: Option<chrono::DateTime<chrono::Utc>>,
}
```

- [ ] **Step 2: Update list_api_keys handler**

When Postgres is available, query from DB. Admins see all, members see their own:

```rust
if let Some(ref pool) = state.db_pool {
    let is_admin = caller_key.as_ref().map_or(false, |k| k.permissions.admin);
    let user_id = caller_key.as_ref()
        .and_then(|k| k.id.strip_prefix("session-"))
        .and_then(|id| uuid::Uuid::parse_str(id).ok());

    let keys = if is_admin {
        sqlx::query_as!(/* ... list all keys ... */)
    } else if let Some(uid) = user_id {
        sqlx::query_as!(/* ... list keys WHERE user_id = uid ... */)
    } else {
        // API key caller — show nothing from Postgres
        vec![]
    };
    // return keys
}
```

- [ ] **Step 3: Update revoke_api_key handler**

When Postgres is available, delete from DB. Admins can revoke any, members only their own.

- [ ] **Step 4: Make generate_api_key public**

In `crates/bigrag-api/src/state.rs`, change `fn generate_api_key()` to `pub fn generate_api_key()`.

- [ ] **Step 5: Verify it compiles**

Run: `cargo check`
Expected: Compiles.

- [ ] **Step 6: Commit**

```bash
git add crates/bigrag-api/src/handlers.rs crates/bigrag-api/src/state.rs
git commit -m "feat: update API key endpoints to use Postgres when configured"
```

---

### Task 18: Final integration test and cleanup

**Files:** Various

- [ ] **Step 1: Run full cargo check and fix any warnings**

Run: `cargo check 2>&1`
Fix any unused import warnings or dead code warnings.

- [ ] **Step 2: Run frontend build**

Run: `cd ui && npx next build`
Fix any type errors.

- [ ] **Step 3: Test backward compatibility (no database)**

Start the backend without `--database-url`:
```bash
cargo run
```

Verify:
- `GET /health` returns 200
- `GET /v1/auth/setup-status` returns 503 "Database not configured"
- Data endpoints work with master key or API keys as before
- Frontend shows login page but setup-status failure falls through to legacy mode

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: final cleanup and backward compatibility fixes"
```
