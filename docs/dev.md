# Development Setup

## Prerequisites

- Rust 1.86+
- Node.js 20+ and pnpm
- Docker (for Postgres and optionally MinIO)

## Start Postgres

User authentication requires Postgres. Start one with Docker:

```bash
docker run -d --name bigrag-pg \
  -e POSTGRES_PASSWORD=bigrag \
  -e POSTGRES_DB=bigrag \
  -p 5432:5432 \
  postgres:17
```

## Start MinIO (optional, for S3 storage)

```bash
docker compose up minio -d
```

MinIO Console: http://localhost:9001 (user: `minioadmin`, password: `minioadmin`)

## Run the Server

```bash
# One-time: copy and edit config
cp bigrag.example.toml bigrag.toml

# With user auth (Postgres)
cargo run -p bigrag-server -- --port 8080 --data-dir ./data \
  --database-url "postgres://postgres:bigrag@localhost:5432/bigrag"

# Without auth (legacy open mode)
cargo run -p bigrag-server -- --port 8080 --data-dir ./data
```

For auto-reload on code changes, install [cargo-watch](https://github.com/watchexec/cargo-watch):

```bash
cargo install cargo-watch
cargo watch -x 'run -p bigrag-server -- --port 8080 --data-dir ./data --database-url "postgres://postgres:bigrag@localhost:5432/bigrag"'
```

API: http://localhost:8080 | Metrics: http://localhost:9090

## Run the UI

```bash
cd ui
pnpm install
pnpm dev
```

Dashboard: http://localhost:3000

On first visit, the UI redirects to `/setup` to create the initial admin account. After that, users log in with email/password. Admins can invite new users from the Users page.

If the server is running without `--database-url`, the UI runs in legacy mode (no login required).

## Verify

```bash
curl http://localhost:8080/health
```
