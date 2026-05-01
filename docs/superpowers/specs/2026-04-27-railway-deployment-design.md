# Railway Deployment Design

## Goal

Provision a single Railway project that hosts the bigRAG API, Studio UI, Postgres, Redis, and Qdrant. Qdrant replaces the previous standalone vector-store stack and runs as one Docker-image service with a persistent volume.

## Services

| Service | Source | Public | Volume | Notes |
|---|---|---:|---|---|
| `Postgres` | Railway plugin | no | managed | Exposes `${{Postgres.DATABASE_URL}}` |
| `Redis` | Railway plugin | no | managed | Exposes `${{Redis.REDIS_URL}}` |
| `bigrag-qdrant` | Docker image `qdrant/qdrant:v1.17.1` | no | 10 GB at `/qdrant/storage` | HTTP on `6333` |
| `bigrag-app` | repo root `/app` | yes | none | Studio UI |
| `bigrag-api` | repo root `/api` | yes | 10 GB at `/data` | FastAPI backend |

## API Environment

```bash
BIGRAG_DATABASE_URL=${{Postgres.DATABASE_URL}}
BIGRAG_REDIS_URL=${{Redis.REDIS_URL}}
BIGRAG_QDRANT_URL=http://${{bigrag-qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333
BIGRAG_QDRANT_CONNECT_TIMEOUT_SECONDS=10
BIGRAG_QDRANT_REQUIRED=false
BIGRAG_UPLOAD_DIR=/data/uploads
```

Use `BIGRAG_QDRANT_API_KEY` only when pointing at Qdrant Cloud or a protected Qdrant instance.

## Acceptance Criteria

1. Qdrant service boots from `qdrant/qdrant:v1.17.1` with storage mounted at `/qdrant/storage`.
2. API `/health` returns `200`.
3. API `/health/ready` reports Postgres, Redis, Qdrant, and embedding provider status.
4. A test collection can ingest a document and return query results.

## Risks

- Qdrant data must be backed up separately from Postgres.
- `BIGRAG_MASTER_KEY` must be stored outside Railway before real provider credentials are entered.
- API startup should leave `BIGRAG_QDRANT_REQUIRED=false` during first deploys so the app can report degraded readiness instead of crash-looping.
