# Running bigRAG

## Prerequisites

- **Docker Compose** (recommended), or **Python 3.12+** (from source)

## Docker Compose (recommended)

```bash
docker compose up -d
```

This starts the full stack:
- bigRAG API on port 8080
- Postgres on port 5432
- Milvus on port 19530

Open http://localhost:3000 for the admin UI (after starting the UI separately), or use the API directly at http://localhost:8080/docs.

## From Source

```bash
# 1. Start infrastructure
docker compose up postgres milvus -d

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
| `BIGRAG_PORT` | Server port | `8080` |
| `BIGRAG_HOST` | Bind address | `0.0.0.0` |
| `BIGRAG_AUTH_REQUIRED` | Enable/disable authentication | `true` |
| `BIGRAG_SECRET_KEY` | Encryption key for secrets at rest | - |
| `BIGRAG_EMBEDDING_PROVIDER` | Default embedding provider | `openai` |
| `BIGRAG_EMBEDDING_MODEL` | Default embedding model | `text-embedding-3-small` |
| `BIGRAG_EMBEDDING_API_KEY` | API key for OpenAI/Cohere embeddings | - |
| `BIGRAG_LOG_LEVEL` | `debug`, `info`, `warning`, `error` | `info` |
| `BIGRAG_UPLOAD_DIR` | Directory for uploaded documents | `./data/uploads` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload file size | `500` |

## Verify

```bash
curl http://localhost:8080/health
```
