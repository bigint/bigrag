# Development Setup

## Prerequisites

- Rust 1.86+
- Node.js 20+ and pnpm
- Docker Compose (for MinIO)

## Start MinIO

```bash
docker compose up minio -d
```

MinIO Console: http://localhost:9001 (user: `minioadmin`, password: `minioadmin`)

## Run the Server

```bash
# One-time: copy and edit config
cp bigrag.example.toml bigrag.toml

# Build and run
cargo run -p bigrag-server -- --port 8080 --data-dir ./data
```

For auto-reload on code changes, install [cargo-watch](https://github.com/watchexec/cargo-watch):

```bash
cargo install cargo-watch
cargo watch -x 'run -p bigrag-server -- --port 8080 --data-dir ./data'
```

API: http://localhost:8080 | Metrics: http://localhost:9090

Default API key: `br_dev_key_change_me` (set via `BIGRAG_API_KEYS` env var)

## Run the UI

```bash
cd ui
pnpm install
pnpm dev
```

Dashboard: http://localhost:3000

## Verify

```bash
curl http://localhost:8080/health
```
