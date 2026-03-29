# Running bigRAG

## Prerequisites

- **Docker** (for Postgres) + **Rust 1.86+** (from source), or **Docker Compose** (all-in-one)

## Quick Start (from source)

```bash
# 1. Start Postgres
docker run -d --name bigrag-pg \
  -e POSTGRES_PASSWORD=bigrag \
  -e POSTGRES_DB=bigrag \
  -p 5432:5432 \
  postgres:17

# 2. Build and run the server
cargo build --release
./target/release/bigrag --port 8080 --data-dir ./data \
  --database-url "postgres://postgres:bigrag@localhost:5432/bigrag"

# 3. Start the UI
cd ui && pnpm install && pnpm dev
```

Open http://localhost:3000 — you'll be prompted to create the initial admin account.

## Without Auth (legacy mode)

To run without user authentication (open access, no login required):

```bash
./target/release/bigrag --port 8080 --data-dir ./data
```

You can optionally set static API keys for programmatic access:

```bash
./target/release/bigrag --port 8080 --data-dir ./data \
  --api-keys "br_dev_key_change_me"
```

## Docker (standalone)

```bash
docker run -d -p 8080:8080 -v $(pwd)/data:/data bigrag/bigrag:latest
```

## UI Dashboard

```bash
cd ui
pnpm install
pnpm dev
```

Opens at http://localhost:3000.

When the server has `--database-url` configured, the UI requires login. On first visit, you create the admin account. Admins can then invite users from the Users page (generates one-time invite links).

When the server runs without `--database-url`, the UI runs in legacy open mode (no login required).

## Verify

```bash
curl http://localhost:8080/health
```

## Configuration

bigRAG reads from `bigrag.toml` or environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_PORT` | Server port | `8080` |
| `BIGRAG_HOST` | Bind address | `0.0.0.0` |
| `BIGRAG_DATABASE_URL` | Postgres URL for user auth (optional) | — |
| `BIGRAG_MASTER_KEY` | Master API key, bypasses all auth | — |
| `BIGRAG_API_KEYS` | Comma-separated API keys (legacy mode) | — |
| `BIGRAG_JWT_SECRET` | HS256 secret for JWT auth (optional) | — |
| `BIGRAG_JWT_ISSUER` | Expected JWT issuer (optional) | — |
| `BIGRAG_STORAGE_BACKEND` | `local`, `s3`, `gcs`, `azure` | `local` |
| `BIGRAG_STORAGE_DATA_DIR` | Data directory | `./data` |
| `BIGRAG_LOG_LEVEL` | `debug`, `info`, `warn`, `error` | `info` |

## Authentication Modes

| Mode | Config | Behavior |
|------|--------|----------|
| **User auth** | `BIGRAG_DATABASE_URL` set | Login required, invite-based signup, roles (admin/member) |
| **API key only** | `BIGRAG_API_KEYS` or `BIGRAG_MASTER_KEY` set | Bearer token auth, no UI login |
| **Open** | Nothing set | All requests allowed, no auth |
