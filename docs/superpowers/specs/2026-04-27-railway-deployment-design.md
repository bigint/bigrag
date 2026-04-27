# Railway Deployment Design — bigRAG

**Date:** 2026-04-27
**Status:** Draft, pending user approval
**Owner:** yoginth@hey.com

## Goal

Provision a single Railway project that hosts the full bigRAG stack — API, Studio admin UI, and every backend dependency (Postgres, Redis, Milvus + etcd) — so the platform is reachable on the public internet from a single deploy. All services run inside Railway; no managed external vector DB.

Non-goal for this spec: CI/CD pipeline, custom domains, monitoring/alerting, multi-region failover, blue-green deploys, automated backups. Those are follow-up specs.

## Scope confirmed with user

- Plan: **Railway Pro** ($20/mo base, required for >8 GB RAM across services).
- Region: **Singapore** (`asia-southeast1` equivalent — closest matching Railway region).
- Vector DB: **Self-hosted Milvus on Railway** (option A in brainstorm — not Zilliz Cloud).
- Execution path: **Chrome MCP driving railway.com** (option B in brainstorm — not Railway CLI).
- OpenAI API key supplied later by user during the env-var step on Railway, not committed anywhere.

## Service topology

Six Railway services in build order. Internal-only services have no public domain; they communicate over Railway's private network via `${{<service>.RAILWAY_PRIVATE_DOMAIN}}` template variables.

| # | Service | Source | Public | Persistent volume | RAM | Notes |
|---|---|---|---|---|---|---|
| 1 | `bigrag-postgres` | Railway PostgreSQL plugin (v17) | no | managed by plugin | plugin default | exposes `DATABASE_URL` |
| 2 | `bigrag-redis` | Railway Redis plugin | no | managed by plugin | plugin default | exposes `REDIS_URL` |
| 3 | `bigrag-etcd` | Docker image `quay.io/coreos/etcd:v3.5.18` | no | 1 GB → `/etcd` | 512 MB | sole consumer is Milvus |
| 4 | `bigrag-milvus` | Docker image `milvusdb/milvus:v2.5.4` | no | 10 GB → `/var/lib/milvus` | 4 GB | depends on etcd |
| 5 | `bigrag-app` | repo build, root `app/` (Next.js 16) | yes | none | 1 GB | provisioned before api so its domain exists for CORS |
| 6 | `bigrag-api` | repo build, Dockerfile at `api/Dockerfile` | yes | 10 GB → `/data` | 4 GB | wires to all five above; CORS references app's domain |

Total reserved RAM: ~10.5 GB (excludes plugin defaults). Pro plan accommodates this; Hobby would not.

## Source builds

- **bigrag-api** — Railway points at the GitHub repo, **Root Directory `/api`**, builder Dockerfile (`Dockerfile` relative to root), watch `api/**`. The shipped Dockerfile hard-codes `--port 4000`, so set Railway's **Custom Start Command** to `python -m bigrag.main --host 0.0.0.0 --port $PORT` to honor Railway's dynamic `$PORT`.
- **bigrag-app** — Railway points at the same repo, **Root Directory `/app`**, builder Nixpacks (no Dockerfile yet). The package.json `start` script hard-codes port 3000, so set Railway's **Custom Start Command** to `next start --port $PORT`. Watch `app/**`.
- **bigrag-etcd / bigrag-milvus** — Docker image source, no build context, image tag pinned exactly as in `docker-compose.yml`.

Pinned versions match `docker-compose.yml` so dev/prod images are identical. If the local compose file bumps versions later, Railway must follow.

## Environment variables

### bigrag-postgres
Plugin manages credentials. Exposes `DATABASE_URL` automatically.

### bigrag-redis
Plugin manages credentials. Exposes `REDIS_URL` automatically.

### bigrag-etcd
| Var | Value |
|---|---|
| `ETCD_AUTO_COMPACTION_MODE` | `revision` |
| `ETCD_AUTO_COMPACTION_RETENTION` | `1000` |
| `ETCD_QUOTA_BACKEND_BYTES` | `4294967296` |
| `ETCD_SNAPSHOT_COUNT` | `50000` |

Start command: `etcd -advertise-client-urls=http://0.0.0.0:2379 -listen-client-urls=http://0.0.0.0:2379 --data-dir=/etcd`

(`127.0.0.1` from compose is replaced with `0.0.0.0` so Milvus on a separate Railway service can reach it.)

### bigrag-milvus
| Var | Value |
|---|---|
| `ETCD_ENDPOINTS` | `${{bigrag-etcd.RAILWAY_PRIVATE_DOMAIN}}:2379` |

Start command: `milvus run standalone`

Note: the `seccomp:unconfined` flag from `docker-compose.yml` cannot be set on Railway. Risk noted in Risks section.

### bigrag-api
| Var | Value |
|---|---|
| `BIGRAG_ENV` | `prod` |
| `BIGRAG_HOST` | `0.0.0.0` |
| `BIGRAG_PORT` | `${{PORT}}` (Railway-provided) |
| `BIGRAG_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `BIGRAG_REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `BIGRAG_MILVUS_URI` | `http://${{bigrag-milvus.RAILWAY_PRIVATE_DOMAIN}}:19530` |
| `BIGRAG_EMBEDDING_PROVIDER` | `openai` |
| `BIGRAG_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `BIGRAG_EMBEDDING_DIMENSION` | `1536` |
| `BIGRAG_EMBEDDING_API_KEY` | user-supplied OpenAI key (set at deploy time, never committed) |
| `BIGRAG_MASTER_KEY` | freshly generated Fernet key (set once at provision time) |
| `BIGRAG_SESSION_COOKIE_SECURE` | `true` |
| `BIGRAG_SESSION_COOKIE_SAMESITE` | `lax` |
| `BIGRAG_CORS_ORIGINS` | `https://${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}` |
| `BIGRAG_LOG_LEVEL` | `info` |
| `BIGRAG_LOG_FORMAT` | `json` |
| `BIGRAG_UPLOAD_DIR` | `/data/uploads` |
| `BIGRAG_INGESTION_WORKERS` | `4` |
| `BIGRAG_DB_POOL_MIN` | `5` |
| `BIGRAG_DB_POOL_MAX` | `50` |
| `BIGRAG_STORAGE_BACKEND` | `local` |

Public domain: Railway-issued `bigrag-api-production-xxxx.up.railway.app`. Custom domain deferred.

### bigrag-app
| Var | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://${{bigrag-api.RAILWAY_PUBLIC_DOMAIN}}` |
| `NODE_ENV` | `production` |

Studio UI talks to the API from the browser, so it must use the public domain (CORS configured on the API to allow the app's public origin).

## Networking model

- Internal mesh: `bigrag-etcd`, `bigrag-milvus`, `bigrag-postgres`, `bigrag-redis` are reachable only via `*.railway.internal`. No public IPs.
- Public surface: `bigrag-api` (REST API + Swagger) and `bigrag-app` (Studio UI).
- API CORS allowlist: the Studio UI's public domain only. `BIGRAG_ENV=prod` hard-rejects `*` wildcard at startup but accepts an empty list (silently breaks the Studio UI in the browser), so the explicit value above is required before the Studio is functional — see Risk #5.

## Volumes & persistence

| Service | Mount | Size | Purpose |
|---|---|---|---|
| `bigrag-etcd` | `/etcd` | 1 GB | Milvus metadata |
| `bigrag-milvus` | `/var/lib/milvus` | 10 GB | vector index + raw vectors |
| `bigrag-api` | `/data` | 10 GB | uploaded source files (`/data/uploads`) |

Postgres/Redis volumes are managed by their Railway plugins.

Volume sizes can be expanded later in Railway UI. No automated backup in this spec — see Risks.

## Cost estimate

Pro plan base: $20/mo.

Resource billing on top (Railway charges per GB-hour and vCPU-hour):

| Service | Avg RAM | Avg vCPU | Approx $/mo idle |
|---|---|---|---|
| postgres plugin | ~512 MB | shared | ~$5 |
| redis plugin | ~512 MB | shared | ~$5 |
| etcd | ~256 MB | 0.1 | ~$2 |
| milvus | ~3 GB | 0.5 | ~$15 |
| api | ~1 GB | 0.3 | ~$8 |
| app | ~512 MB | 0.1 | ~$3 |

Idle estimate: **$58/mo** including base. Real usage will increase API/Milvus draw during ingestion. Volume storage at $0.25/GB/mo adds ~$8/mo for the 31 GB above.

## Provisioning vs first-boot

**Provisioning order** (Railway service creation, runs once):

1. Project created in Singapore region.
2. Postgres plugin added.
3. Redis plugin added.
4. `bigrag-etcd` service created (Docker image, volume attached, env set, no public domain).
5. `bigrag-milvus` service created (Docker image, volume attached, env set, no public domain).
6. `bigrag-app` service created from repo (`app/` root). Railway assigns a `*.up.railway.app` domain immediately even before the first build completes. This domain is needed in step 7.
7. `bigrag-api` service created from repo (`api/Dockerfile`), with `BIGRAG_CORS_ORIGINS` referencing the app's public domain via `${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}`.

**First-boot order** (Railway resolves dependencies and brings services up):

1. Postgres plugin healthy.
2. Redis plugin healthy.
3. etcd healthy.
4. Milvus healthy (depends on etcd).
5. API boots: Alembic stamp-or-upgrade runs against Postgres, Milvus connection verified, Redis ping verified.
6. Studio UI boots, smoke-fetches `/health` on the API.
7. User opens Studio UI, hits `/setup`, creates first admin account. No shared-secret env var path exists per project conventions.

## Out of scope

- CI/CD via GitHub Actions for Railway (manual deploys via Railway's auto-deploy on git push instead).
- Custom domain + TLS for api/app.
- Monitoring (Grafana/Datadog) and alerting.
- Automated Postgres / Milvus backups beyond Railway plugin defaults.
- Multi-environment (staging/prod) split — single environment for now.
- Horizontal scaling of API or worker pools beyond a single replica.

## Risks

1. **Milvus seccomp** — `docker-compose.yml` runs Milvus with `seccomp:unconfined`. Railway does not expose seccomp config. On modern kernels Milvus 2.5 starts without it, but a regression in a future Milvus image may surface as crash-on-boot. Mitigation: pin to `v2.5.4`, watch logs on first deploy, fall back to a previous tag if needed.
2. **etcd single-node** — etcd is a single replica with no quorum. A volume corruption loses Milvus metadata (vectors are recoverable from raw embeddings, but indexes need rebuild). Acceptable for v0; revisit before production traffic.
3. **No automated backup** — Postgres plugin has Railway's built-in retention; Milvus volume has none. Acceptable for v0; backup spec is a follow-up.
4. **OpenAI key in Railway env** — visible to anyone with project Editor access. Rotate via OpenAI dashboard if leaked. Master key (Fernet) is generated fresh per project; losing it loses the ability to decrypt provider secrets stored in Postgres, so it must be backed up out-of-band before any production data is ingested.
5. **Studio UI ↔ API CORS** — `BIGRAG_CORS_ORIGINS` must point at the Studio UI's public domain before the Studio is usable from a browser. The API's prod startup guard (`api/bigrag/startup_guard.py`) only refuses on `*` wildcard, not on an empty list, so the API will boot either way; an empty list silently rejects every cross-origin request and the Studio UI breaks at runtime. Mitigation: provision `bigrag-app` before `bigrag-api` so Railway assigns it a public domain, then reference that domain via `${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}` in the API's `BIGRAG_CORS_ORIGINS` (template vars resolve at deploy time, not at service-creation time).
6. **Region** — Railway's Singapore region availability is service-dependent (some plugins are US-only). If Postgres or Redis plugins aren't offered in Singapore, fallback is `asia-southeast1` for compute and US-East for plugins, accepting cross-region latency on DB calls. Verify at provisioning time.

## Success criteria

- `curl https://<api-public>/health` returns 200 with `{"status":"ok"}`.
- Studio UI loads at `https://<app-public>` and `/setup` accepts admin creation.
- After admin creation, a test document upload succeeds end-to-end (PDF → ingestion → searchable).
- No service has been restarted unexpectedly in the first 30 minutes of operation.
- Total monthly cost projection within 20% of $58 estimate after one week of idle.

## Open questions

None blocking. User-supplied OpenAI key is deferred to provisioning step by user request; design accommodates a missing key (API boots, ingestion fails clearly, Studio UI shows actionable error).
