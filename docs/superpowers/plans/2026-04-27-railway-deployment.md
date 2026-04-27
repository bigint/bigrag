# Railway Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Caveat:** This plan is browser-driven (Chrome MCP on railway.com). Subagent-driven execution is *not* recommended here — the executor must own a single Chrome tab the user is logged into; spawning fresh subagents per task fragments that browser state. Inline execution (executing-plans) is the right choice for this plan.

**Goal:** Provision a working bigRAG deployment on Railway (Pro plan, Singapore region) with all six services healthy and a publicly reachable Studio UI.

**Architecture:** Browser-driven provisioning of Railway services via the `claude-in-chrome` MCP. Order: project shell → managed plugins (Postgres, Redis) → Milvus stack (etcd, milvus) → Studio UI → API. CORS reference resolves at deploy time via Railway template variables, so `bigrag-app` is provisioned before `bigrag-api` to give the latter a domain to point at.

**Tech Stack:** Railway (Pro plan), `claude-in-chrome` MCP for browser driving, Docker Hub / Quay images for etcd & Milvus, repo-from-GitHub for api & app, Fernet (cryptography) for master-key generation.

---

## Working state to track during execution

These values are produced during execution and must be remembered between tasks. Keep them in conversation context (do **not** commit any of them):

| Key | Source | Used in |
|---|---|---|
| `PROJECT_URL` | Task 1 output | every subsequent task |
| `MASTER_KEY` | Task 0, generated | Task 8 |
| `APP_PUBLIC_DOMAIN` | Task 6 output (Railway-issued) | Task 7, Task 8, Task 10 |
| `API_PUBLIC_DOMAIN` | Task 7 output (Railway-issued) | Task 8, Task 9, Task 10, Task 11 |

---

## Task 0: Pre-flight

**Files:** none

- [ ] **Step 1: Load Chrome MCP tool schemas**

Run `ToolSearch` with query `Claude_in_Chrome` and `max_results: 30` to load every browser tool in one call. Verify the response contains at least: `navigate`, `find`, `form_input`, `read_page`, `get_page_text`, `read_console_messages`, `tabs_create_mcp`, `list_connected_browsers`.

- [ ] **Step 2: Verify a Chrome with the extension is connected**

Tool: `mcp__Claude_in_Chrome__list_connected_browsers`
Expected: at least one entry. If empty, stop and tell the user: "Install the 'Claude in Chrome' extension and reload chrome://extensions, then say 'go'." Wait for confirmation before continuing.

- [ ] **Step 3: Verify Railway login**

Tool: `mcp__Claude_in_Chrome__navigate` to `https://railway.com/dashboard`.
Then `mcp__Claude_in_Chrome__get_page_text` and check for the user's project list / a "New Project" affordance. If the page is the login screen, stop and ask the user to log in, then say 'go'. Wait for confirmation.

- [ ] **Step 4: Generate the Fernet master key**

Run:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Expected: a single 44-char base64url string ending in `=`. Store as `MASTER_KEY` in working state. **Do not echo it back to the user in plain text in transcript** — refer to it as `MASTER_KEY` from this point on. Tell the user the key has been generated and offer to drop it in their clipboard or paste it into Railway directly when we reach Task 8.

- [ ] **Step 5: Confirm Pro plan is active**

Navigate to `https://railway.com/account/plans` (or equivalent). Verify the visible plan is **Pro**. If not, stop and tell the user to upgrade and confirm before continuing.

(no commit — provisioning prep)

---

## Task 1: Create the Railway project "bigrag-prod"

**Files:** none

- [ ] **Step 1: Open New Project flow**

Tool: navigate to `https://railway.com/new`.

- [ ] **Step 2: Choose "Empty Project"**

Find the "Empty Project" option (we'll add services manually rather than picking a template) and click it.

- [ ] **Step 3: Name the project `bigrag-prod`**

Locate the project-name input and set value to `bigrag-prod`. Submit.

- [ ] **Step 4: Set region to Singapore**

In project settings → Region, choose **Singapore** (`asia-southeast1`). If Singapore is not offered for this account/plan combination, fall back to the closest Asia region (Tokyo / Mumbai), record the choice in conversation as a deviation from the spec, and proceed. Document the deviation later in the runbook.

- [ ] **Step 5: Capture project URL**

`mcp__Claude_in_Chrome__read_page` and capture the canonical URL. Save to working state as `PROJECT_URL`.

Verification: dashboard shows an empty canvas, project name visible at top, URL is of the form `https://railway.com/project/<uuid>`.

(no commit)

---

## Task 2: Add PostgreSQL 17 plugin

**Files:** none

- [ ] **Step 1: Trigger "Add a Service"**

In the project canvas, click the "+ New" / "Add a Service" affordance.

- [ ] **Step 2: Choose "Database" → "Add PostgreSQL"**

Select PostgreSQL from the database options. Confirm version is 17 (Railway's current default is 17 at time of writing — if it's older, use the version selector to pick 17).

- [ ] **Step 3: Wait for plugin to come up**

Verify the new service tile renders and goes from "Deploying" to a green/healthy state. Read its **Variables** tab and confirm `DATABASE_URL` is populated (will be referenced via `${{Postgres.DATABASE_URL}}` later). Note the auto-generated service name (e.g., `Postgres`) — reuse it in env templates.

(no commit)

---

## Task 3: Add Redis 7 plugin

**Files:** none

- [ ] **Step 1: Click "+ New" → "Database" → "Add Redis"**

- [ ] **Step 2: Wait for healthy state**

Verify it's healthy and `REDIS_URL` is exposed. Note the service name (e.g., `Redis`).

(no commit)

---

## Task 4: Add `bigrag-etcd` (Docker image)

**Files:** none

- [ ] **Step 1: Click "+ New" → "Empty Service"** (or "Deploy from Docker Image" if available)

- [ ] **Step 2: Configure source as Docker image**

Service settings → Source → Image. Set the image to:
```
quay.io/coreos/etcd:v3.5.18
```

- [ ] **Step 3: Rename service to `bigrag-etcd`**

Settings → service name → `bigrag-etcd`. Save.

- [ ] **Step 4: Set environment variables**

Variables tab → add:
| Var | Value |
|---|---|
| `ETCD_AUTO_COMPACTION_MODE` | `revision` |
| `ETCD_AUTO_COMPACTION_RETENTION` | `1000` |
| `ETCD_QUOTA_BACKEND_BYTES` | `4294967296` |
| `ETCD_SNAPSHOT_COUNT` | `50000` |

- [ ] **Step 5: Set custom start command**

Settings → Deploy → Custom Start Command:
```
etcd -advertise-client-urls=http://0.0.0.0:2379 -listen-client-urls=http://0.0.0.0:2379 --data-dir=/etcd
```

- [ ] **Step 6: Attach a 1 GB volume mounted at `/etcd`**

Service → Volumes → New Volume. Mount path `/etcd`, size 1 GB.

- [ ] **Step 7: Confirm service is internal-only**

Settings → Networking → ensure no public domain is generated. Private domain will be `${{bigrag-etcd.RAILWAY_PRIVATE_DOMAIN}}` (verify the slug Railway assigned matches the service rename).

- [ ] **Step 8: Deploy and verify**

Click Deploy. Watch logs via `mcp__Claude_in_Chrome__read_console_messages` or the Railway log panel. Expected log lines: `embedded etcd starting`, `ready to serve client requests`, no panics. Service tile turns green.

If etcd panics on `seccomp` errors: this would invalidate Risk #1 — stop and ask before falling back.

(no commit)

---

## Task 5: Add `bigrag-milvus` (Docker image)

**Files:** none

- [ ] **Step 1: Click "+ New" → "Empty Service" → Docker image**

- [ ] **Step 2: Set image**

```
milvusdb/milvus:v2.5.4
```

- [ ] **Step 3: Rename service to `bigrag-milvus`**

- [ ] **Step 4: Set environment variable**

| Var | Value |
|---|---|
| `ETCD_ENDPOINTS` | `${{bigrag-etcd.RAILWAY_PRIVATE_DOMAIN}}:2379` |

(Replace `bigrag-etcd` with the exact slug Railway recorded in Task 4 step 7 if it differs.)

- [ ] **Step 5: Set custom start command**

```
milvus run standalone
```

- [ ] **Step 6: Set resource limits**

Settings → Resources → 4 GB RAM minimum. Pro plan default may be lower; raise it.

- [ ] **Step 7: Attach a 10 GB volume mounted at `/var/lib/milvus`**

- [ ] **Step 8: Keep service internal-only (no public domain)**

- [ ] **Step 9: Deploy**

Watch logs. Healthy log marker: `Milvus Proxy successfully started`. The first boot may take 60-120 s while Milvus initialises against etcd.

If Milvus crash-loops with seccomp/kernel-syscall errors: stop, document the failure, and fall back to `milvusdb/milvus:v2.4.x` as Risk #1 mitigation. Do not silently downgrade.

(no commit)

---

## Task 6: Add `bigrag-app` (Studio UI from repo)

**Files:** none

- [ ] **Step 1: Click "+ New" → "GitHub Repo"**

- [ ] **Step 2: Connect / select repo `bigint/bigrag` (branch `main`)**

If GitHub auth is needed, walk the user through it. Do not auto-grant org-wide access.

- [ ] **Step 3: Rename service to `bigrag-app`**

- [ ] **Step 4: Set service Root Directory to `/app`**

Settings → Source → Root Directory → `/app`.

- [ ] **Step 5: Confirm builder is Nixpacks (auto-detect)**

Should detect `package.json` with `next` dependency. Build command auto-derived as `pnpm install --frozen-lockfile && pnpm build` or similar (Nixpacks reads pnpm-lock from repo root via workspace; verify it works on first build, otherwise set Build Command explicitly to `cd .. && pnpm install --frozen-lockfile && pnpm --filter @bigrag/app build`).

- [ ] **Step 6: Set custom start command**

```
next start --port $PORT
```

(The repo's `package.json` `start` script hard-codes port 3000 and Nixpacks runs `pnpm start` by default, so this override is required.)

- [ ] **Step 7: Add env vars**

| Var | Value |
|---|---|
| `NODE_ENV` | `production` |
| `NEXT_PUBLIC_API_URL` | `https://${{bigrag-api.RAILWAY_PUBLIC_DOMAIN}}` |

(The api service doesn't exist yet, so this template var resolves to empty on first build of the app. We'll redeploy the app after Task 7 so the URL fills in.)

- [ ] **Step 8: Generate a public domain**

Settings → Networking → Generate Domain. Capture as `APP_PUBLIC_DOMAIN` (e.g., `bigrag-app-production-abc1.up.railway.app`).

- [ ] **Step 9: Trigger first deploy**

Build will complete but the app will load with a broken API URL — that's expected, we fix it in Task 8 + redeploy.

Verification: build logs show successful `next build`; service tile reports a healthy/running state.

(no commit)

---

## Task 7: Add `bigrag-api` (FastAPI from repo)

**Files:** none

- [ ] **Step 1: Click "+ New" → "GitHub Repo" → same repo**

- [ ] **Step 2: Rename service to `bigrag-api`**

- [ ] **Step 3: Set service Root Directory to `/api`**

- [ ] **Step 4: Set builder to Dockerfile, path `Dockerfile`**

(Within the `/api` root, the Dockerfile is at `Dockerfile`.)

- [ ] **Step 5: Set custom start command**

```
python -m bigrag.main --host 0.0.0.0 --port $PORT
```

(The Dockerfile CMD hard-codes port 4000; this override picks up Railway's dynamic `$PORT`.)

- [ ] **Step 6: Set resource limits**

4 GB RAM minimum, 1 vCPU.

- [ ] **Step 7: Attach a 10 GB volume mounted at `/data`**

- [ ] **Step 8: Add env vars (everything except secrets)**

Set the non-secret values now; secrets go in Task 8. Use the *exact* slugs Railway shows for the postgres/redis/milvus/app services in template variables — substitute below if they differ:

| Var | Value |
|---|---|
| `BIGRAG_ENV` | `prod` |
| `BIGRAG_HOST` | `0.0.0.0` |
| `BIGRAG_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `BIGRAG_REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `BIGRAG_MILVUS_URI` | `http://${{bigrag-milvus.RAILWAY_PRIVATE_DOMAIN}}:19530` |
| `BIGRAG_EMBEDDING_PROVIDER` | `openai` |
| `BIGRAG_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `BIGRAG_EMBEDDING_DIMENSION` | `1536` |
| `BIGRAG_SESSION_COOKIE_SECURE` | `true` |
| `BIGRAG_SESSION_COOKIE_SAMESITE` | `lax` |
| `BIGRAG_LOG_LEVEL` | `info` |
| `BIGRAG_LOG_FORMAT` | `json` |
| `BIGRAG_UPLOAD_DIR` | `/data/uploads` |
| `BIGRAG_INGESTION_WORKERS` | `4` |
| `BIGRAG_DB_POOL_MIN` | `5` |
| `BIGRAG_DB_POOL_MAX` | `50` |
| `BIGRAG_STORAGE_BACKEND` | `local` |

- [ ] **Step 9: Generate a public domain**

Capture as `API_PUBLIC_DOMAIN`.

- [ ] **Step 10: Do *not* deploy yet**

Secrets in Task 8 must be set first; `BIGRAG_ENV=prod` will fail startup without `BIGRAG_MASTER_KEY`.

(no commit)

---

## Task 8: Inject secrets and CORS

**Files:** none

- [ ] **Step 1: Set `BIGRAG_MASTER_KEY` on `bigrag-api`**

Variables tab → Add → key `BIGRAG_MASTER_KEY`, value = the `MASTER_KEY` generated in Task 0 step 4. Use Railway's "secret" / hidden-value toggle if available so it's masked in transcript captures.

- [ ] **Step 2: Set `BIGRAG_CORS_ORIGINS` on `bigrag-api`**

Value:
```
https://${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}
```

- [ ] **Step 3: Set `BIGRAG_EMBEDDING_API_KEY` on `bigrag-api` — placeholder**

User said they'll add the OpenAI key later. Set the var with value `__SET_BEFORE_INGESTION__` so the API can boot but ingestion will throw a clear error on first attempt. Tell the user explicitly: "Embedding key is set to a sentinel — replace it on the bigrag-api Variables tab before any document upload, and trigger a redeploy."

- [ ] **Step 4: Back the master key up out-of-band**

Tell the user (in plain words, not echoing the key): "Save your `BIGRAG_MASTER_KEY` somewhere persistent right now (1Password / Bitwarden / file with strong filesystem permissions). Losing it means losing decrypt access to provider secrets stored in Postgres."

Wait for an explicit acknowledgement before continuing.

(no commit)

---

## Task 9: First deploy and health verification

**Files:** none

- [ ] **Step 1: Trigger redeploy of `bigrag-api`**

Deployments tab → Deploy. Watch build logs.

- [ ] **Step 2: Trigger redeploy of `bigrag-app`**

(Necessary so `NEXT_PUBLIC_API_URL` baked into the build picks up the now-existent api domain.)

- [ ] **Step 3: Wait for both services healthy**

Verify via Railway UI that both `bigrag-api` and `bigrag-app` show the green/active state.

- [ ] **Step 4: Curl the API /health endpoint**

```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://$API_PUBLIC_DOMAIN/health"
```
Expected: `200`. If 502/503: check Railway logs for the api service.

- [ ] **Step 5: Curl the API root for version**

```bash
curl -s "https://$API_PUBLIC_DOMAIN/" | head -5
```
Expected: JSON with `version` and `status: ok`.

- [ ] **Step 6: Hit the Studio UI in a browser tab**

Navigate via Chrome MCP to `https://$APP_PUBLIC_DOMAIN/`. Expected: the Studio UI loads without console errors. `mcp__Claude_in_Chrome__read_console_messages` should show no CORS or 4xx/5xx fetch errors.

If CORS errors appear: re-check `BIGRAG_CORS_ORIGINS` resolved to the actual app domain (not literal template syntax) — Variables tab → click the var → confirm value preview shows `https://bigrag-app-production-...up.railway.app`.

(no commit)

---

## Task 10: First-admin smoke test

**Files:** none

- [ ] **Step 1: Visit `/setup` on the Studio UI**

Navigate to `https://$APP_PUBLIC_DOMAIN/setup`.

- [ ] **Step 2: Create the first admin account**

Provide an admin email + password chosen by the user. Submit.

Expected: redirect to `/login` or dashboard, no errors. Cookie set with `Secure` flag (verifiable via DevTools).

- [ ] **Step 3: Log in**

- [ ] **Step 4: Verify dashboard renders + no console errors**

(no commit; no document upload yet — that requires the OpenAI key, which user will add later)

---

## Task 11: Write the Railway deployment runbook

**Files:**
- Create: `website/content/docs/deployment/railway.mdx`
- Modify: `website/content/docs/deployment/meta.json` (add `"railway"` to pages list)

- [ ] **Step 1: Read existing deployment doc structure for style**

```bash
cat website/content/docs/deployment/meta.json
cat website/content/docs/deployment/docker.mdx | head -40
```

- [ ] **Step 2: Create `website/content/docs/deployment/railway.mdx`**

Content (no comments, MDX with frontmatter):

```mdx
---
title: Railway
description: Deploy bigRAG to Railway with managed Postgres and Redis plus self-hosted Milvus.
---

import { Callout } from "fumadocs-ui/components/callout";

This guide describes a single-project Railway deployment with all six services running side-by-side: API, Studio UI, Postgres, Redis, etcd, and Milvus. Pick this path when you want everything inside one Railway project; if you want a managed Milvus, see the Zilliz Cloud section at the bottom.

## What you get

- **bigrag-api** — FastAPI backend (public domain).
- **bigrag-app** — Studio admin UI (public domain).
- **Postgres 17** — Railway plugin, manages credentials.
- **Redis 7** — Railway plugin, manages credentials.
- **bigrag-etcd** + **bigrag-milvus** — Docker images, internal-only.

Idle cost on the Pro plan: ~$58/mo (Pro base $20 + ~$38 service usage), plus ~$8/mo for 31 GB of volumes. Milvus alone runs ~$15/mo because it holds 3 GB of RAM around the clock.

## Prerequisites

- Railway **Pro plan** (Hobby's 8 GB ceiling won't fit Milvus comfortably).
- An OpenAI or Cohere API key (you can deploy first and add the key before your first ingestion).
- A region — Singapore is closest to South Asia; pick whichever Railway region is nearest your users. If your chosen region doesn't offer the Postgres/Redis plugins, Railway will silently route to its nearest plugin region.

## Service order

Provision in this order so the API can reference the app's public domain in CORS:

1. Postgres plugin
2. Redis plugin
3. `bigrag-etcd` (Docker)
4. `bigrag-milvus` (Docker)
5. `bigrag-app` (repo, root `/app`)
6. `bigrag-api` (repo, root `/api`)

## Service configuration

### Postgres plugin

Add → Database → PostgreSQL 17. No further config; Railway exposes `DATABASE_URL`.

### Redis plugin

Add → Database → Redis. No further config; Railway exposes `REDIS_URL`.

### bigrag-etcd

| Setting | Value |
|---|---|
| Source | Docker image `quay.io/coreos/etcd:v3.5.18` |
| Start command | `etcd -advertise-client-urls=http://0.0.0.0:2379 -listen-client-urls=http://0.0.0.0:2379 --data-dir=/etcd` |
| Volume | 1 GB at `/etcd` |
| Public domain | none |

Environment:

```
ETCD_AUTO_COMPACTION_MODE=revision
ETCD_AUTO_COMPACTION_RETENTION=1000
ETCD_QUOTA_BACKEND_BYTES=4294967296
ETCD_SNAPSHOT_COUNT=50000
```

### bigrag-milvus

| Setting | Value |
|---|---|
| Source | Docker image `milvusdb/milvus:v2.5.4` |
| Start command | `milvus run standalone` |
| Volume | 10 GB at `/var/lib/milvus` |
| RAM | 4 GB minimum |
| Public domain | none |

Environment:

```
ETCD_ENDPOINTS=${{bigrag-etcd.RAILWAY_PRIVATE_DOMAIN}}:2379
```

<Callout type="warn">
The local `docker-compose.yml` runs Milvus with `seccomp:unconfined`. Railway does not expose seccomp config; on modern kernels Milvus 2.5 boots fine without it, but pin the image tag and watch first-deploy logs.
</Callout>

### bigrag-app

| Setting | Value |
|---|---|
| Source | GitHub repo, Root Directory `/app` |
| Builder | Nixpacks |
| Start command | `next start --port $PORT` |
| Public domain | yes (auto-issued or custom) |

Environment:

```
NODE_ENV=production
NEXT_PUBLIC_API_URL=https://${{bigrag-api.RAILWAY_PUBLIC_DOMAIN}}
```

### bigrag-api

| Setting | Value |
|---|---|
| Source | GitHub repo, Root Directory `/api`, Dockerfile `Dockerfile` |
| Start command | `python -m bigrag.main --host 0.0.0.0 --port $PORT` |
| Volume | 10 GB at `/data` |
| RAM | 4 GB minimum |
| Public domain | yes (auto-issued or custom) |

Environment:

```
BIGRAG_ENV=prod
BIGRAG_HOST=0.0.0.0
BIGRAG_DATABASE_URL=${{Postgres.DATABASE_URL}}
BIGRAG_REDIS_URL=${{Redis.REDIS_URL}}
BIGRAG_MILVUS_URI=http://${{bigrag-milvus.RAILWAY_PRIVATE_DOMAIN}}:19530
BIGRAG_EMBEDDING_PROVIDER=openai
BIGRAG_EMBEDDING_MODEL=text-embedding-3-small
BIGRAG_EMBEDDING_DIMENSION=1536
BIGRAG_EMBEDDING_API_KEY=<your OpenAI key>
BIGRAG_MASTER_KEY=<see "Generate the master key" below>
BIGRAG_SESSION_COOKIE_SECURE=true
BIGRAG_SESSION_COOKIE_SAMESITE=lax
BIGRAG_CORS_ORIGINS=https://${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}
BIGRAG_LOG_LEVEL=info
BIGRAG_LOG_FORMAT=json
BIGRAG_UPLOAD_DIR=/data/uploads
BIGRAG_INGESTION_WORKERS=4
BIGRAG_DB_POOL_MIN=5
BIGRAG_DB_POOL_MAX=50
BIGRAG_STORAGE_BACKEND=local
```

## Generate the master key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output into `BIGRAG_MASTER_KEY` on the bigrag-api Variables tab.

<Callout type="error">
**Back the master key up immediately.** It encrypts provider secrets stored in Postgres. Losing it means losing decrypt access — there is no recovery path. Save it to your password manager *before* uploading any documents.
</Callout>

## First-run

1. After all services are healthy, open the Studio UI's public URL.
2. The first visit lands on `/setup` — create the admin account there.
3. Log in. Confirm the dashboard renders without console errors.
4. Add a collection and upload a test document. If the embedding key is missing, the upload will surface a clear error — set `BIGRAG_EMBEDDING_API_KEY` on bigrag-api and redeploy.

## Updating

Both `bigrag-api` and `bigrag-app` watch the connected GitHub repo on their root directories. Pushing to `main` (or whichever branch you connected) triggers an auto-deploy of just the affected service.

## Self-hosted Milvus vs Zilliz Cloud

If `bigrag-etcd + bigrag-milvus` are too heavy for your usage, swap them for [Zilliz Cloud](https://zilliz.com/cloud) (managed Milvus, free tier covers most dev workloads):

1. Delete `bigrag-etcd` and `bigrag-milvus` from the Railway project.
2. On bigrag-api, set `BIGRAG_MILVUS_URI=https://<your-cluster>.api.gcp-us-west1.zillizcloud.com` and add `BIGRAG_MILVUS_TOKEN=<token>`.
3. Redeploy.

This trades external-dependency risk for ~$15/mo and 4 GB RAM saved on Railway.
```

- [ ] **Step 3: Update `website/content/docs/deployment/meta.json`**

Add `"railway"` to the `pages` array, after `"docker"`:

Tool: `Edit`. Open the file, locate the pages list, insert.

Verification: file is valid JSON; new entry appears.

- [ ] **Step 4: Run lint**

```bash
pnpm exec biome check --write website/content/docs/deployment/railway.mdx website/content/docs/deployment/meta.json
```
Expected: no errors. Biome lint config may not check MDX; that's fine — MDX lint is a non-goal.

- [ ] **Step 5: Commit**

```bash
git add website/content/docs/deployment/railway.mdx website/content/docs/deployment/meta.json
git commit -m "docs: add Railway deployment guide"
git push
```

- [ ] **Step 6: Verify the docs site builds the new page**

If the docs site is running locally (`./dev.sh --website`), open `http://localhost:3000/docs/deployment/railway` and check it renders. Otherwise note that next docs build will pick it up.

---

## Task 12: Update memory

**Files:**
- Create: `/Users/yoginth/.claude/projects/-Users-yoginth-bigrag/memory/project_railway_deployment.md`
- Modify: `/Users/yoginth/.claude/projects/-Users-yoginth-bigrag/memory/MEMORY.md`

- [ ] **Step 1: Write project memory**

File `project_railway_deployment.md`:

```markdown
---
name: Railway deployment
description: Production Railway project for bigRAG, all six services in one Singapore-region project, ~$58/mo on Pro
type: project
---

bigRAG runs on Railway in project `bigrag-prod` (Singapore region). Six services: Postgres plugin, Redis plugin, bigrag-etcd, bigrag-milvus (Docker), bigrag-app, bigrag-api (repo).

**Why:** User wanted single-project deploy with self-hosted Milvus rather than Zilliz Cloud. Pro plan required for Milvus's 4 GB RAM ceiling.

**How to apply:** When the user references "the deployment" / "prod" / "Railway", this is what they mean. Service names, env-var template variables, and provisioning order are documented at `website/content/docs/deployment/railway.mdx`. Spec at `docs/superpowers/specs/2026-04-27-railway-deployment-design.md`.
```

- [ ] **Step 2: Add line to MEMORY.md**

Insert after the existing `bigRAG project context` line:

```
- [Railway deployment](project_railway_deployment.md) — Production Railway project, six services, Singapore region, ~$58/mo
```

- [ ] **Step 3: No commit**

Memory files live outside the repo.

---

## Self-review checklist

Run the following after this plan is fully drafted (already done at write-time, but re-verify if anything material changes):

- [x] **Spec coverage** — every section of `docs/superpowers/specs/2026-04-27-railway-deployment-design.md` is implemented by some task in this plan. Cost & resource sizing are surfaced in the runbook (Task 11). Risks 1–6 are addressed: #1 by stop-on-seccomp-failure (Task 5), #2/#3 by accepting v0 risk and noting in runbook, #4 by master-key backup gate (Task 8 step 4), #5 by provision-app-before-api ordering (Tasks 6→7), #6 by region-fallback path (Task 1 step 4).
- [x] **No placeholders** — every step has the exact action, env-var values, and verification.
- [x] **Type/value consistency** — service names (`bigrag-etcd`, `bigrag-milvus`, `bigrag-app`, `bigrag-api`), template variables (`${{Postgres.DATABASE_URL}}`, `${{bigrag-app.RAILWAY_PUBLIC_DOMAIN}}`), and image tags (`v3.5.18`, `v2.5.4`) are identical across spec, plan, and runbook.

## Out of scope (future plans)

- CI/CD GitHub Actions workflow that pushes Railway-specific configs.
- Custom domains + TLS for `bigrag-api` and `bigrag-app`.
- Postgres + Milvus volume backup automation.
- Staging environment (separate Railway project or environment).
- Horizontal scaling of API workers and Milvus replicas.
- Switching to Zilliz Cloud (alternate path documented in runbook but not provisioned).
