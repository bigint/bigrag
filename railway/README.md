# bigRAG Railway Template

This directory contains the repo-owned pieces for the Railway template composer.

Use these exact service names unless you also update the variable references:

| Service | Type | Config file | Variables |
|---|---|---|---|
| `Postgres` | Railway Postgres | Railway managed | Railway managed |
| `Redis` | Railway Redis | Railway managed | Railway managed |
| `API` | GitHub service | `/railway/api.json` | `railway/variables/api.env` |
| `Worker` | GitHub service | `/railway/worker.json` | `railway/variables/worker.env` |
| `App` | GitHub service | `/railway/app.json` | `railway/variables/app.env` |

Set the `API`, `Worker`, and `App` source repo to this repository. The config files use Dockerfiles from the monorepo root, so the Railway config file path must be absolute from the repository root.

Fill these required values before the first deploy:

| Variable | Services | Value |
|---|---|---|
| `BIGRAG_MASTER_KEY` | `API`, `Worker` | Fernet key from `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BIGRAG_TURBOPUFFER_API_KEY` | `API`, `Worker` | Turbopuffer API key |
| `BIGRAG_EMBEDDING_API_KEY` | `API`, `Worker` | OpenAI, Cohere, Voyage, or OpenAI-compatible embedding key |

Enable public HTTP networking for `API` and `App`. Leave `Worker`, `Postgres`, and `Redis` private. Ingestion staging is local-only, so the API and worker need the same mounted upload directory when they run as separate services.

## Worker concurrency

`Worker` runs `bigrag-worker --processes ${BIGRAG_WORKER_PROCESSES:-1} --threads ${BIGRAG_WORKER_THREADS:-8}`. The template sets `BIGRAG_WORKER_PROCESSES=1` for a small instance (local dev and Docker Compose default to `5`). Raise `BIGRAG_WORKER_PROCESSES` on the `Worker` service as you scale the box — it is the same env var across every environment.

## Dedicated cache Redis

The managed `Redis` serves both the job broker and the response cache. At higher load this is a hazard: cache eviction can drop queued jobs. Add a second Railway Redis service named `RedisCache`, then set `BIGRAG_CACHE_REDIS_URL=${{RedisCache.REDIS_URL}}` on both `API` and `Worker`. Do this before raising sustained ingestion throughput. It is deliberately left out of `variables/*.env` because the reference cannot resolve until the `RedisCache` service exists.
