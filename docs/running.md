# Running bigRAG

## Prerequisites

- **Docker Compose** (recommended), or **Python 3.12+** (from source)

## Docker Compose (recommended)

```bash
docker compose up -d
```

This starts the full stack:
- Admin UI on port 5000
- bigRAG API on port 6000
- Postgres on port 5432
- Redis on port 6379
- Milvus on port 19530

Open http://localhost:5000 for the admin UI, or use the API directly at http://localhost:6000/docs.

### Docker Images

Pre-built images are published to Docker Hub on every push to `main`:

```bash
docker pull yoginth/bigrag:latest      # API
docker pull yoginth/bigrag-ui:latest   # Admin UI
```

## From Source

```bash
# 1. Start infrastructure
docker compose up postgres redis milvus -d

# 2. Install and run the backend
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m bigrag.main \
  --database-url "postgres://bigrag:bigrag@localhost:5432/bigrag" \
  --milvus-uri "http://localhost:19530"

# 3. Start the UI
cd ui && pnpm install && pnpm dev
```

## Authentication Modes

| Mode | Config | Behavior |
|------|--------|----------|
| **User auth** (default) | `BIGRAG_AUTH_REQUIRED=true` | Login required, DB-managed API keys, roles (admin/member) |
| **No auth** | `BIGRAG_AUTH_REQUIRED=false` | All requests allowed as anonymous admin (self-hosted) |

## Configuration

bigRAG reads from `bigrag.toml` or environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_DATABASE_URL` | Postgres connection URL | `postgres://bigrag:bigrag@localhost:5432/bigrag` |
| `BIGRAG_MILVUS_URI` | Milvus connection URI | `http://localhost:19530` |
| `BIGRAG_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `BIGRAG_PORT` | Server port | `6000` |
| `BIGRAG_WORKERS` | Uvicorn workers | `4` |
| `BIGRAG_AUTH_REQUIRED` | Enable/disable authentication | `true` |
| `BIGRAG_SECRET_KEY` | Encryption key for secrets at rest | — |
| `BIGRAG_LOG_LEVEL` | Log level (`debug`, `info`, `warning`, `error`) | `info` |
| `BIGRAG_INGESTION_WORKERS` | Background processing workers | `4` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload file size | `1024` |

Embedding provider, model, and API key are configured per collection via the API or admin UI.

## Verify

```bash
curl http://localhost:6000/health
# → {"status":"ok","version":"0.x.x","postgres":true,"milvus":true,"redis":true}
```
