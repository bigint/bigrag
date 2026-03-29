# Running bigRAG

## Prerequisites

- **Docker Compose** (recommended) or **Rust 1.86+** (from source)

## Docker Compose (recommended)

Starts bigRAG with MinIO for S3-compatible object storage:

```bash
docker compose up -d
```

| Service | URL |
|---------|-----|
| bigRAG API | http://localhost:8080 |
| Metrics | http://localhost:9090 |
| MinIO API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |

Default API key: `br_dev_key_change_me`

To stop:

```bash
docker compose down
```

## From Source

```bash
cargo build --release
./target/release/bigrag --port 8080 --data-dir ./data
```

Optionally copy and edit the config file:

```bash
cp bigrag.example.toml bigrag.toml
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

## Verify

```bash
curl http://localhost:8080/health
```

## Configuration

bigRAG reads from `bigrag.toml` or environment variables prefixed with `BIGRAG_`:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_PORT` | Server port | `8080` |
| `BIGRAG_HOST` | Bind address | `0.0.0.0` |
| `BIGRAG_STORAGE_BACKEND` | `local`, `s3`, `gcs`, `azure` | `local` |
| `BIGRAG_STORAGE_DATA_DIR` | Data directory | `./data` |
| `BIGRAG_LOG_LEVEL` | `debug`, `info`, `warn`, `error` | `info` |
| `BIGRAG_API_KEYS` | Comma-separated API keys | — |
