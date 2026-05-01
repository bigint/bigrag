# Railway Deployment Plan

## Summary

Deploy bigRAG to Railway with managed Postgres and Redis plus a single self-hosted Qdrant service. The Qdrant service replaces the previous multi-service vector-store setup and only needs one persistent volume.

## Tasks

1. Create the Railway project and choose the target region.
2. Add the Postgres plugin.
3. Add the Redis plugin.
4. Add `bigrag-qdrant` as Docker image `qdrant/qdrant:v1.17.1`.
5. Attach a 10 GB volume to `bigrag-qdrant` at `/qdrant/storage`.
6. Add `bigrag-app` from repo root `/app`.
7. Add `bigrag-api` from repo root `/api` using `/api/Dockerfile`.
8. Configure API variables:

```bash
BIGRAG_DATABASE_URL=${{Postgres.DATABASE_URL}}
BIGRAG_REDIS_URL=${{Redis.REDIS_URL}}
BIGRAG_QDRANT_URL=http://${{bigrag-qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333
BIGRAG_QDRANT_CONNECT_TIMEOUT_SECONDS=10
BIGRAG_QDRANT_REQUIRED=false
BIGRAG_UPLOAD_DIR=/data/uploads
```

9. Generate and store `BIGRAG_MASTER_KEY`.
10. Deploy and verify `/health`, `/health/ready`, first admin setup, document upload, and query.

## Notes

- Qdrant Cloud can replace the Railway Qdrant service by setting `BIGRAG_QDRANT_URL` and `BIGRAG_QDRANT_API_KEY`.
- Keep `BIGRAG_QDRANT_REQUIRED=false` during initial rollout so Qdrant issues show as degraded readiness instead of blocking the API from booting.
- Back up Qdrant storage and Postgres independently.
