# Running bigRAG

## Prerequisites

- **Docker Compose** (recommended), or **Python 3.12+** (from source)

## Docker Compose (recommended)

```bash
docker compose up -d
```

This starts the full stack:
- bigRAG API on port 6100
- Postgres on port 5432
- Redis on port 6379
- Milvus on port 19530

Open http://localhost:6100/docs for the API documentation.

### Docker Images

Pre-built images are published to Docker Hub on every push to `main`:

```bash
docker pull yoginth/bigrag:latest
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
```

## Authentication

Set the `BIGRAG_API_SECRET` environment variable to protect the API with a shared secret. All requests must include `Authorization: Bearer <secret>`. If `BIGRAG_API_SECRET` is not set, the API is open to all requests.

## Configuration

bigRAG reads from `bigrag.toml` or environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_DATABASE_URL` | Postgres connection URL | `postgres://bigrag:bigrag@localhost:5432/bigrag` |
| `BIGRAG_MILVUS_URI` | Milvus connection URI | `http://localhost:19530` |
| `BIGRAG_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `BIGRAG_PORT` | Server port | `6100` |
| `BIGRAG_WORKERS` | Uvicorn workers | `4` |
| `BIGRAG_API_SECRET` | Shared API secret (open access if unset) | — |
| `BIGRAG_LOG_LEVEL` | Log level (`debug`, `info`, `warning`, `error`) | `info` |
| `BIGRAG_INGESTION_WORKERS` | Background processing workers | `4` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload file size | `1024` |

Embedding provider, model, and API key are configured per collection via the API.

## Verify

```bash
curl http://localhost:6100/health
# → {"status":"ok","version":"0.x.x","postgres":true,"milvus":true,"redis":true}
```
