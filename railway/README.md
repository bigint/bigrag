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

The managed `Redis` serves both the job broker and the response cache. At higher load, add a second Railway Redis (e.g. `RedisCache`) and set `BIGRAG_CACHE_REDIS_URL=${{RedisCache.REDIS_URL}}` on `API` and `Worker` so cache eviction can never drop queued jobs.
