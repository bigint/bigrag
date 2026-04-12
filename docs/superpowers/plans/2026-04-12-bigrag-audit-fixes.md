# bigRAG Audit Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close critical gaps from the 2026-04-12 platform audit — security hardening, production readiness, and missing AI-company RAG features — so bigRAG is safe to self-host and viable to adopt in place of Pinecone / Ragie / Vectara.

**Architecture:** Three execution layers. **P0** = bugs and security issues we fix in the current codebase with surgical PRs + TDD. **P1** = new capabilities (retrieval quality, SDK, observability) that extend existing services. **P2 / Big-bets** = tracked as a structured backlog — each item gets expanded into its own task plan just-in-time, before execution, so we don't speculate on code we won't touch for weeks.

**Tech Stack:** Python 3.12 / FastAPI / asyncpg / pymilvus / Docling / structlog / prometheus_client / Redis · TypeScript SDK / Next.js 16 Studio UI / Fumadocs site.

**Execution order:** P0-1 → P0-10 top-down. Each is a standalone commit. After all P0 items land, checkpoint with the user before expanding any P1 item into a detailed plan.

---

## Table of contents

1. [P0 — Critical bugs & security (execute now)](#p0--critical-bugs--security-execute-now)
2. [P1 — Must-have features for AI-company adoption (backlog, detailed on pickup)](#p1--must-have-features-for-ai-company-adoption)
3. [P2 — Nice-to-have & enterprise-readiness](#p2--nice-to-have--enterprise-readiness)
4. [Big bets — speculative / high-leverage](#big-bets--speculative--high-leverage)
5. [Remove / simplify](#remove--simplify)

Every P0 task has full TDD steps. P1/P2/Big-bet items have description, acceptance criteria, and impacted files — enough to write the detailed plan when we pick it up.

---

## P0 — Critical bugs & security (execute now)

### Task P0-1: Redact secrets in all structured logs

**Why:** Today no logger logs `api_key` directly, but the risk is structural — any future `logger.info(body)` or `logger.error(f"config={collection}")` would leak OpenAI / Cohere / S3 credentials into stdout, log aggregators, and crash dumps. A blanket structlog processor makes leaks impossible by construction.

**Files:**
- Modify: `api/bigrag/logging.py` (add `redact_secrets` processor, insert into `shared_processors`)
- Test: `api/tests/test_logging.py` (new file)

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_logging.py
from __future__ import annotations

import io
import json
import logging

import pytest

from bigrag.logging import configure_logging, get_logger


@pytest.fixture
def json_log_capture(monkeypatch):
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    configure_logging(log_level="info", log_format="json")
    # swap the stream so we capture
    for h in logging.getLogger().handlers:
        h.stream = buf
    yield buf


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "embedding_api_key",
        "s3_secret_key",
        "password",
        "session_token",
        "authorization",
    ],
)
def test_redacts_sensitive_fields(json_log_capture, key):
    logger = get_logger("bigrag.test")
    logger.info("event", **{key: "super-secret-value", "safe": "ok"})
    line = json_log_capture.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload[key] == "[REDACTED]"
    assert payload["safe"] == "ok"


def test_redacts_nested_dict(json_log_capture):
    logger = get_logger("bigrag.test")
    logger.info("event", config={"api_key": "sk-abc", "model": "text-3-small"})
    line = json_log_capture.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["config"]["api_key"] == "[REDACTED]"
    assert payload["config"]["model"] == "text-3-small"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd api && uv run pytest tests/test_logging.py -v
```

Expected: FAIL — `api_key` appears verbatim in output.

- [ ] **Step 3: Implement the processor**

Edit `api/bigrag/logging.py`. Before `configure_logging`, add:

```python
_SENSITIVE_KEYS = {
    "api_key",
    "embedding_api_key",
    "rerank_api_key",
    "s3_access_key",
    "s3_secret_key",
    "aws_access_key_id",
    "aws_secret_access_key",
    "password",
    "password_hash",
    "session_token",
    "token",
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "signing_secret",
}


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact(v) for v in value)
    return value


def redact_secrets(logger, method_name, event_dict):
    return _redact(event_dict)  # type: ignore[return-value]
```

Then in `shared_processors`, insert `redact_secrets` immediately before the timestamper:

```python
shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    redact_secrets,
    structlog.processors.TimeStamper(fmt="%H:%M:%S" if log_format == "text" else "iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.UnicodeDecoder(),
]
```

- [ ] **Step 4: Run tests**

```bash
cd api && uv run pytest tests/test_logging.py -v
```

Expected: PASS all parametrised cases.

- [ ] **Step 5: Commit**

```bash
git add api/bigrag/logging.py api/tests/test_logging.py
git commit -m "feat: redact sensitive fields in structured logs"
```

---

### Task P0-2: Make document upload transactional

**Why:** `routers/documents.py:136-163` writes the row first, then enqueues the ingestion job outside the transaction. If Redis drops the connection between the two, the document row lingers in `pending` status forever with no worker. With outbox-pattern ordering (enqueue first, then insert, roll back on enqueue failure), we either get both or neither.

Simpler path taken here: re-order so we enqueue **after** the DB row exists but tolerate enqueue failure by setting `status='failed'` and logging. The cost is one extra UPDATE vs. pure outbox, but it's honest: the doc shows up in the list with a clear failure reason rather than hanging.

**Files:**
- Modify: `api/bigrag/routers/documents.py:135-163`
- Modify: `api/bigrag/routers/documents.py:155-163` (enqueue block)
- Test: `api/tests/test_documents.py` (new test added to existing file)

- [ ] **Step 1: Write the failing test**

```python
# Add to api/tests/test_documents.py
@pytest.mark.asyncio
async def test_upload_marks_failed_when_enqueue_errors(monkeypatch, test_client, test_collection):
    """If Redis enqueue fails after DB insert, the document must end up status=failed."""
    from bigrag.services.queue import ingestion_queue

    async def boom(*args, **kwargs):
        raise RuntimeError("redis unreachable")

    monkeypatch.setattr(ingestion_queue, "enqueue", boom)

    resp = test_client.post(
        f"/v1/collections/{test_collection['name']}/documents",
        files={"file": ("hello.txt", b"hi", "text/plain")},
    )
    # Endpoint returns 503 — but doc row is now status=failed with error populated
    assert resp.status_code in (503, 500)

    # Verify doc row exists and is marked failed
    from bigrag.database import db
    row = await db.fetchrow(
        "SELECT status, error FROM documents WHERE collection_id = $1 ORDER BY created_at DESC LIMIT 1",
        test_collection["id"],
    )
    assert row["status"] == "failed"
    assert "enqueue" in (row["error"] or "").lower()
```

- [ ] **Step 2: Run test**

```bash
cd api && uv run pytest tests/test_documents.py::test_upload_marks_failed_when_enqueue_errors -v
```

Expected: FAIL — current behaviour leaves `status=pending`.

- [ ] **Step 3: Implement the fix**

Replace the block at `api/bigrag/routers/documents.py:155-163`:

```python
try:
    await ingestion_queue.enqueue(
        create_ingestion_job(
            document_id=doc_id,
            file_path=storage_key,
            collection_name=collection_name,
            collection=collection,
            fallback_api_key=settings.embedding_api_key,
        )
    )
except Exception as exc:
    logger.exception("upload: enqueue failed, marking document failed", doc_id=doc_id)
    await db.execute(
        "UPDATE documents SET status = 'failed', error = $2, updated_at = now() WHERE id = $1",
        uuid.UUID(doc_id),
        f"enqueue failed: {exc.__class__.__name__}",
    )
    raise HTTPException(
        status_code=503,
        detail="Ingestion queue unavailable — document saved as failed, retry later.",
    ) from exc
```

- [ ] **Step 4: Run test**

Expected: PASS. Also re-run the full document test file: `uv run pytest tests/test_documents.py -v`.

- [ ] **Step 5: Commit**

```bash
git add api/bigrag/routers/documents.py api/tests/test_documents.py
git commit -m "fix: surface enqueue failure as document.status=failed instead of zombie pending"
```

---

### Task P0-3: Replace broad `except Exception: pass/continue`

**Why:** Five sites swallow all exceptions silently, which is why documents sometimes get stuck "processing" with no user-visible error. Each needs the exception logged and the relevant status surfaced.

**Sites (from grep):**
1. `api/bigrag/services/conversion.py:27-28` — HF cache check (benign, keep quiet but log at debug).
2. `api/bigrag/services/s3_client.py:60-61` and `73-74` — credential resolution fallback.
3. `api/bigrag/services/vector_store.py:61-62` — connection teardown in reconnect loop.
4. `api/bigrag/services/queue.py:104-105` — flush_collection inner loop.

**Files:**
- Modify: `api/bigrag/services/conversion.py`, `s3_client.py`, `vector_store.py`, `queue.py`
- Test: `api/tests/test_exception_handling.py` (new)

- [ ] **Step 1: Write a test for the queue.flush_collection case (highest impact)**

```python
# api/tests/test_exception_handling.py
import pytest
from bigrag.services.queue import IngestionJob, ingestion_queue


@pytest.mark.asyncio
async def test_flush_collection_logs_malformed_job(caplog, fakeredis_client):
    await ingestion_queue.connect(fakeredis_client)
    await fakeredis_client.rpush("bigrag:ingestion:queue", b"not-json-at-all")
    removed = await ingestion_queue.flush_collection("my-coll")
    assert removed == 0
    assert any(
        "malformed job payload" in rec.message for rec in caplog.records
    ), "expected malformed payload to be logged, not silently skipped"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd api && uv run pytest tests/test_exception_handling.py -v
```

- [ ] **Step 3: Fix queue.py:104-105**

```python
try:
    job = IngestionJob.deserialize(item)
except (ValueError, TypeError, KeyError) as exc:
    logger.warning("queue: malformed job payload, skipping", error=str(exc))
    continue
if job.collection_name == collection_name:
    await self._redis.lrem(QUEUE_KEY, 1, item)
    removed += 1
```

- [ ] **Step 4: Apply the same pattern to the other four sites**

- `conversion.py:27-28`: catch `(OSError, ValueError)` and `logger.debug("hf cache check failed", error=str(exc))`.
- `s3_client.py:60-61, 73-74`: catch `(botocore.exceptions.BotoCoreError, ClientError)` and log at debug (fall-through is intentional).
- `vector_store.py:61-62`: catch `(pymilvus.exceptions.MilvusException, ConnectionError)` and `logger.warning("vector_store: disconnect during teardown", error=str(exc))`.

- [ ] **Step 5: Run all service tests, commit**

```bash
cd api && uv run pytest tests/ -v
git add api/bigrag/services api/tests/test_exception_handling.py
git commit -m "fix: replace broad except blocks with typed logging"
```

---

### Task P0-5: `Idempotency-Key` header + TypeScript SDK support

**Why:** Production API callers retry on network blips. Without idempotency, a retried POST `/documents` creates two docs, a retried collection create returns 409, a retried webhook creation duplicates. Stripe's `Idempotency-Key` convention is the industry standard.

**Behaviour:**
- On any mutating verb (POST/PUT/PATCH/DELETE), if header `Idempotency-Key` is present, middleware looks up Redis key `idem:<sha256(key+user_id+path)>`. Hit → replay the cached response. Miss → run handler, cache `{status, headers, body}` with 24h TTL.
- Only 2xx responses are cached (4xx/5xx left uncached so clients can retry with the same key after fixing input).
- TS SDK: accept `idempotencyKey` in client config and per-request options. Auto-generate a UUID for mutating calls if not provided.

**Files:**
- Create: `api/bigrag/middleware/idempotency.py`
- Modify: `api/bigrag/main.py` (install middleware)
- Modify: `sdks/typescript/src/core.ts` (attach header, allow override)
- Modify: `sdks/typescript/src/client.ts` (accept `idempotencyKey` in options)
- Test: `api/tests/test_idempotency.py`, `sdks/typescript/tests/idempotency.test.ts`

**Acceptance criteria:**
- Replaying the same `Idempotency-Key` on `POST /v1/collections` returns the first response byte-for-byte (same body, same 201 status), no second row created.
- `Idempotency-Key-Replayed: true` response header on replays.
- SDK's `client.collections.create(...)` auto-attaches a UUID for retries.

_(Full TDD steps will be added when this task is picked up. Skeleton: write middleware test → write middleware → write SDK test → wire `createClient({ idempotencyKey })` option → ship.)_

---

### Task P0-6: Per-API-key rate limiting

**Why:** A single leaked `bigrag_sk_...` can exhaust a customer's OpenAI credits in minutes. Rate limits are table-stakes for any key-based API.

**Design:**
- Token-bucket in Redis (`limit:<key_id>:<window>`) with sliding window.
- Defaults: `/query` 60 req/min, `/documents` upload 10 req/min, everything else 120 req/min.
- Per-key overrides stored in `api_keys.rate_limits jsonb` column (add via migration).
- Response on throttle: 429 + `Retry-After` + `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers.

**Files:**
- Create: `api/bigrag/middleware/rate_limit.py`
- Migration: add `rate_limits jsonb DEFAULT '{}'::jsonb` to `api_keys` table in `database.py`
- Modify: `api/bigrag/main.py` (install middleware after auth)
- Test: `api/tests/test_rate_limit.py`

**Acceptance:** Sending 61 requests/min on `/query` with the same API key: request 61 returns 429 with correct headers; request 62 after 60s succeeds again.

---

### Task P0-7: Whitelist dynamic SQL field names

**Why:** `services/s3_ingest.py:131-140` builds an `UPDATE ... SET` clause by interpolating `fields.keys()` into an f-string. Today only internal callers feed this — but a single refactor that adds a user-derived key turns it into SQL injection. A small allowlist neutralises the risk permanently.

**Files:**
- Modify: `api/bigrag/services/s3_ingest.py:131-141`
- Test: `api/tests/test_s3_ingest.py` (new or append)

**Acceptance:**
- Allowed field names: `{"processed", "total_found", "skipped", "error_message", "last_key"}` (derive by inspecting current call sites).
- Passing any other key raises `ValueError("unknown job field: <name>")` before SQL runs.
- Existing functional tests still pass.

_(Detailed TDD steps on pickup: test rejects unknown key → replace f-string with a dispatch over the allowlist → test both known and unknown cases.)_

---

### Task P0-8: File upload mime sniffing + zip-bomb guard

**Why:** Current validation (`routers/documents.py:39-58`) trusts the file extension. Malicious user uploads `evil.exe` renamed `report.pdf` → parsed as PDF, Docling throws, document stuck failed. Worse: an uploaded 1 KB zip file that decompresses to 4 GB (for docx/pptx/epub) can OOM the worker.

**Design:**
- Add `python-magic` dependency. After reading the upload, call `magic.from_buffer(content[:4096], mime=True)` and assert it matches the declared extension (using a fixed map).
- For zip-based formats (`.docx`, `.pptx`, `.xlsx`, `.epub`), open with `zipfile.ZipFile` and sum `zinfo.file_size` across entries; reject if > `max_decompressed_mb` (default 500).

**Files:**
- Modify: `api/bigrag/routers/documents.py:39-120`
- Modify: `api/pyproject.toml` (add `python-magic`; note the libmagic system dep in README)
- Test: `api/tests/test_upload_validation.py`

**Acceptance:**
- Uploading `.exe` renamed `.pdf` → 400 "file content does not match extension".
- Uploading a zip bomb `.docx` (<1 MB, decompresses to 1 GB) → 400 "archive too large when decompressed".
- Legitimate PDFs, DOCXs still work.

---

### Task P0-9: `POST /v1/auth/logout-all`

**Why:** Password-change already revokes all sessions (`routers/auth.py:182`). There's no user-initiated equivalent — if you lose a device or suspect a compromised session, you can only change password. Logout-all is a one-line DB operation and a standard settings-page button.

**Files:**
- Modify: `api/bigrag/routers/auth.py` (add endpoint)
- Modify: `app/src/app/(dashboard)/settings/page.tsx` (add "Sign out everywhere" button)
- Modify: `sdks/typescript/src/resources/` (or wherever auth lives) — add `client.auth.logoutAll()`
- Test: `api/tests/test_auth.py` (append)

**Acceptance:**
- Calling endpoint invalidates all sessions for the current user; current cookie is also cleared.
- `GET /v1/auth/me` after logout-all returns 401.
- Studio button shows a confirmation dialog then signs out and redirects to `/login`.

---

### Task P0-10: Startup safety guard for insecure defaults

**Why:** `docker-compose.yml` ships with `POSTGRES_PASSWORD=bigrag`, `BIGRAG_SESSION_COOKIE_SECURE=false`, and empty-by-default CORS. If someone copies the compose file to a public VM, they self-own. A boot-time check that refuses to start the API in production mode without minimum hardening is cheap insurance.

**Design:**
- New env var `BIGRAG_ENV` with values `dev` / `prod` (default `dev`).
- In `lifespan` startup, if `BIGRAG_ENV=prod`:
    - `session_cookie_secure` must be `true`.
    - `cors_origins` must not contain `*`.
    - `POSTGRES_PASSWORD != "bigrag"` (or sniff by connecting and checking — simpler: require `BIGRAG_ALLOW_DEFAULT_DB_PASSWORD=1` to override).
    - Warn (don't fail) if no admin exists yet.
- Failure mode: log the full remediation checklist, exit 1.

**Files:**
- Modify: `api/bigrag/config.py` (add `env: Literal["dev", "prod"] = "dev"`)
- Modify: `api/bigrag/main.py` (add startup guard)
- Modify: `docker-compose.yml` (add `BIGRAG_ENV: prod` example in a commented "production override" block)
- Modify: `website/content/docs/deployment/production.mdx` (document the flag)
- Test: `api/tests/test_startup_guard.py`

**Acceptance:**
- Starting with `BIGRAG_ENV=prod` and `cors_origins=["*"]` → process exits 1 with clear error.
- Starting with `BIGRAG_ENV=prod` and all guards satisfied → boots normally.
- `BIGRAG_ENV=dev` (default) → no checks, as before.

---

## P1 — Must-have features for AI-company adoption

Each item is described well enough to plan and execute in a day or two. When we're about to pick one up, we expand it to a full TDD-task plan following the P0 format.

### Retrieval quality

- [ ] **P1-R1: MMR diversity on result sets.** Add `diversity: float = 0.0` to `/query` body. When >0, apply MMR over top-k*3 initial results, keep top-k. Knob trades relevance for diversity. Files: `services/retrieval.py`. Tests: near-duplicate-chunks fixture.
- [ ] **P1-R2: HyDE query expansion.** Flag `hyde: true` generates a hypothetical answer via OpenAI, embeds *that*, searches with it. 2-5× recall on underspecified queries in our domain. Files: `services/retrieval.py` + new `services/hyde.py`.
- [ ] **P1-R3: RRF score normalisation.** Today hybrid fuses raw ranks. Add option `hybrid_strategy: "rrf" | "weighted" | "normalized"`. Files: `services/retrieval.py`.
- [ ] **P1-R4: Persist page + char-offset citations.** Docling exposes `DocItem.prov`. Store `page_no`, `char_start`, `char_end`, `bbox` as scalar fields in Milvus and in the query response. Files: `services/ingestion.py`, `services/vector_store.py` schema, `routers/query.py` response model. Big value for LLM citations.
- [ ] **P1-R5: Faceted search.** Aggregate counts by metadata field in the query response, driven by a `facets: ["field_a", "field_b"]` request param. Files: `services/retrieval.py`, `routers/query.py`.
- [ ] **P1-R6: Query-phase latency breakdown in response.** Return `{embed_ms, search_ms, rerank_ms, total_ms}`. Cheap to add, powers the Studio playground debugger. Files: `services/retrieval.py`, `routers/query.py`.

### Ingestion

- [ ] **P1-I1: Recursive / semantic chunker option.** Collection config key `chunk_strategy: "paragraph" | "recursive" | "semantic"`. Recursive uses separators with overlap; semantic uses sentence embeddings to detect topic breaks. Files: `services/ingestion.py`.
- [ ] **P1-I2: Preserve tables and images.** Don't flatten Docling's structured output to plain text. Store tables as separate chunks with a `chunk_type: "table"` field (markdown rendering). For images, optionally caption via a vision model (feature-flagged). Files: `services/ingestion.py`, `services/conversion.py`.
- [ ] **P1-I3: Content-hash dedup.** Compute sha256 of upload bytes, store in `documents.content_hash`. On upload, if hash already exists in the collection, return 200 with the existing doc_id and `deduped: true`. Files: `routers/documents.py`, migration.
- [ ] **P1-I4: Chunk-level retry with exponential backoff.** Today a failed chunk fails the whole document. Store chunk status per chunk_id, retry individually up to 3 times with backoff. Files: `services/ingestion.py`, `services/queue.py`, migration for `chunk_retries` table.
- [ ] **P1-I5: Streaming / tail S3 sync.** Persist S3 `ContinuationToken`, schedule delta runs by Redis-streams schedule (hourly/daily). Files: `services/s3_ingest.py`.

### Embeddings

- [ ] **P1-E1: BYO embedding endpoint (OpenAI-compatible).** New provider type `openai_compatible` with `base_url` + `model`. Unlocks Ollama, vLLM, TEI, Bedrock via LiteLLM, Vertex. Files: `services/embedding.py`, `models/embedding_preset.py`.
- [ ] **P1-E2: Persistent embedding cache.** Content-hash → vector cached in Postgres (or Redis with LRU eviction). Skips API calls on re-embed / re-ingest. Files: `services/embedding.py`, new `embedding_cache` table. Cuts cost 30-70% on iterative workloads.
- [ ] **P1-E3: Token-accurate truncation + warning.** Use `tiktoken` to count tokens before request; truncate to model max (with `utf-8` safety) and surface `warnings: ["input_truncated"]` in ingestion response. Files: `services/embedding.py`.
- [ ] **P1-E4: `/v1/usage` cost endpoint.** Query `embedding_tokens_total` via Prometheus (or read log of embedding calls) and return per-day, per-collection, per-provider token and dollar figures using a rate card. Files: new `routers/usage.py`.

### Vector store

- [ ] **P1-V1: Pluggable backend.** Extract a `VectorStore` protocol with `upsert`, `search`, `delete`, `filter_search`. Ship alternate implementation: **pgvector** (zero-infra for small deployments). Qdrant can come later. Files: `services/vector_store.py` → `services/vector_stores/{milvus,pgvector}.py`.
- [ ] **P1-V2: HNSW index option.** Collection config `index_type: "IVF_FLAT" | "HNSW"` with tuned `M` and `efConstruction`. IVF is fine <1M vectors; above that HNSW wins. Files: `services/vector_store.py`.
- [ ] **P1-V3: Milvus partition per collection tenant.** Partition-by-tenant gives 10-50× filter speedup for multi-tenant SaaS. Requires `tenant_id` metadata field convention. Files: `services/vector_store.py`.

### Auth & multi-tenancy

- [ ] **P1-A1: Scoped API keys.** `permissions` column already exists — unused. Scopes: `{collection:read, collection:write, document:upload, query:read, admin:*}`. Key creation UI and middleware enforcement. Files: `models/auth.py`, `middleware/auth.py`, `routers/admin_api_keys.py`, `app/src/app/(dashboard)/api-keys/page.tsx`.
- [ ] **P1-A2: Audit log.** `audit_log` table with `{id, actor_id, action, resource_type, resource_id, metadata, created_at, ip, user_agent}`. Decorator on sensitive endpoints. `GET /v1/audit` for admins with filters. Files: new migration, new `middleware/audit.py`, new router, Studio page.
- [ ] **P1-A3: OAuth / OIDC / SSO login.** Google + GitHub + generic OIDC provider on the Studio `/login` page. Files: new `routers/oauth.py`, `app/src/app/(auth)/login/page.tsx`.
- [ ] **P1-A4: Workspaces (multi-tenancy).** `workspace_id` on every owned resource; current single-tenant deployment becomes "default workspace". Invite flow, member list, workspace switcher in UI. Big change — may want its own full plan document.

### Webhooks

- [ ] **P1-W1: Delivery-log UI + replay.** `GET /v1/webhooks/:id/deliveries` returns paginated list. Studio renders the table; a "Replay" button re-fires with the stored payload. Files: `routers/webhooks.py`, `app/src/app/(dashboard)/webhooks/[id]/page.tsx`.
- [ ] **P1-W2: Test-fire endpoint.** `POST /v1/webhooks/:id/test` sends a synthetic event. Return delivery response inline. Files: `routers/webhooks.py`, Studio button.
- [ ] **P1-W3: Standard signature headers.** Rename header to `X-BigRAG-Signature` + add `X-BigRAG-Event` and `X-BigRAG-Delivery-Id`. Keep old header as alias for one release. Document verification code in Python, Node, Go. Files: `services/webhook.py`, docs.

### Observability (beyond P0-4)

- [ ] **P1-O1: OpenTelemetry traces.** Auto-instrument FastAPI + asyncpg + redis + httpx. Request ID flows through Redis queue into worker logs. Files: `main.py`, `services/queue.py`, `pyproject.toml`.
- [ ] **P1-O2: Sentry integration.** `sentry-sdk` with FastAPI + structlog integrations, opt-in via `BIGRAG_SENTRY_DSN`. Files: `main.py`.
- [ ] **P1-O3: Studio usage dashboard.** Chart embedding spend, query volume, ingestion throughput per collection over 24h / 7d / 30d. Files: `app/src/app/(dashboard)/overview/page.tsx`, new `routers/usage.py` endpoints.

### SDK

- [ ] **P1-S1: OpenAPI-generated types in TS SDK.** Wire `openapi-typescript` → check in generated types. Kill manual drift. Files: `sdks/typescript/scripts/generate.ts`, CI.
- [ ] **P1-S2: `onUploadProgress` callback** for file uploads. Use `XMLHttpRequest` or `undici` events. Files: `sdks/typescript/src/core.ts`.
- [ ] **P1-S3: Cursor pagination helpers.** `client.documents.list().autoPaginate()` async iterator. Files: `sdks/typescript/src/resources/documents.ts`.
- [ ] **P1-S4: React hooks package `@bigrag/react`.** `useCollections`, `useDocuments`, `useQuery` built on TanStack Query. Files: new workspace `sdks/react/`.
- [ ] **P1-S5: Python SDK async audit + docs.** Confirm the existing Python SDK has async support, streaming, and error hierarchy parity; surface it prominently in README and docs. Files: `sdks/python/`, `website/content/docs/sdks/python.mdx`.
- [ ] **P1-S6: Go SDK.** Ops teams self-hosting want one. Generate from OpenAPI. Files: new `sdks/go/`.

### Studio UI

- [ ] **P1-U1: Query debugger in playground.** Per-phase latency (embed / ANN / rerank) bars; raw vector scores per chunk; filter hit counts; "why this chunk" inspector. Files: `app/src/app/(dashboard)/playground/page.tsx`, new response fields from P1-R6.
- [ ] **P1-U2: Chunk viewer on document detail.** Show all chunks with page number and content, highlight chunks that match a test query typed in a side panel. Files: `app/src/app/(dashboard)/collections/[name]/documents/[docId]/page.tsx`.
- [ ] **P1-U3: Re-embed collection button.** Switches model, re-runs embedding over existing chunks (no re-parse). Progress shown via SSE. Files: `routers/collections.py` (new endpoint), `services/ingestion.py` (re-embed-only code path), Studio page.
- [ ] **P1-U4: Bulk upload UI.** Drag-folder, multi-file, CSV-of-URLs, progress per file. Files: `app/src/app/(dashboard)/collections/[name]/upload/page.tsx`.
- [ ] **P1-U5: Dark-mode toggle.** Wire a provider + a header toggle; audit all `bg-card`, `text-foreground` usage. Files: `app/src/app/layout.tsx`, `app/src/components/ui/theme-toggle.tsx`.
- [ ] **P1-U6: Accessibility pass.** Add `aria-label` to all icon buttons, skip-to-content link, focus-visible rings, keyboard navigation through the sidebar. Files: across `app/src/components/` and all dashboard pages.

### Docs

- [ ] **P1-D1: "Migrate from Pinecone" guide.** Full API-to-API mapping + a one-shot importer script (read from Pinecone, upsert to bigRAG). Files: `website/content/docs/migration/from-pinecone.mdx` + `examples/migrate_from_pinecone.py`.
- [ ] **P1-D2: "Migrate from Ragie" + "Migrate from Vectara" guides.** Same shape. Files: `website/content/docs/migration/...`.
- [ ] **P1-D3: Production hardening checklist.** TLS termination, reverse proxy (Caddy sample), secret rotation, backup/restore (pg_dump + Milvus backup tool), DR plan, scaling topology. Files: `website/content/docs/deployment/production.mdx` (expand).
- [ ] **P1-D4: Architecture deep-dive.** Why Milvus + Postgres split, why Docling, sequence diagrams for upload/query/webhook flows. Files: `website/content/docs/concepts/architecture.mdx`.
- [ ] **P1-D5: Benchmarks page.** Query latency and recall on MS MARCO + BEIR, compared to Pinecone and Weaviate (link external sources where apples-to-apples isn't possible). Files: `website/content/docs/benchmarks.mdx`.
- [ ] **P1-D6: Cookbook: multi-tenant SaaS.** Patterns for isolation, per-tenant API keys, usage metering. Files: `website/content/docs/cookbook/multi-tenant-saas.mdx`.

---

## P2 — Nice-to-have & enterprise-readiness

- [ ] **P2-E1: Helm chart.** k8s-native deploy. Blocker for F500 adopters. New `deploy/helm/bigrag/`.
- [ ] **P2-E2: Terraform module (AWS/GCP).** Reference infra with managed Postgres + Milvus on Zilliz Cloud. New `deploy/terraform/`.
- [ ] **P2-E3: One-click deploy templates.** Fly.io `fly.toml`, Railway `railway.json`, Render `render.yaml`. Each linked from README.
- [ ] **P2-E4: CI runs full e2e.** Extend `.github/workflows/test.yml` to spin up Postgres+Redis+Milvus services and run `e2e/run.py`.
- [ ] **P2-E5: PII detection on ingest.** Optional `redact_pii: true` collection flag using presidio; emails / phones / CC numbers redacted before embedding. New `services/pii.py`.
- [ ] **P2-E6: Content moderation on upload.** Optional call to OpenAI moderation (or local classifier) before enqueue; reject or flag. New `services/moderation.py`.
- [ ] **P2-E7: GDPR delete.** `DELETE /v1/users/:id?cascade=true` cascades to collections → documents → Milvus vectors. Returns a deletion certificate. New `routers/gdpr.py`.
- [ ] **P2-E8: Built-in eval runner.** Upload a JSONL of `(query, expected_doc_ids)` pairs; compute recall@k, mrr, ndcg per retrieval config. New `routers/eval.py`, UI page.
- [ ] **P2-E9: Metadata schema + validation.** Collection-level JSON schema for metadata; reject invalid metadata on upload. Enables faceted-search type safety.
- [ ] **P2-E10: Query cost caps / quotas.** Per-API-key and per-workspace dollar caps; soft warn at 80%, hard block at 100%. Needs P1-E4.

---

## Big bets — speculative / high-leverage

- [ ] **BB1: Graph-RAG mode.** Entity extraction on ingest (spaCy or LLM), edges in Postgres, hybrid graph+vector retrieve. Matches 2025's big LangChain / LlamaIndex wave. New `services/graph.py`, new `/v1/collections/:name/graph` endpoints.
- [ ] **BB2: Agentic retrieval endpoint.** `POST /v1/agent/query` that loops retrieve → reason → refine, returning a final answer + citations + tool trace. Streams tokens. New `routers/agent.py` + provider abstraction.
- [ ] **BB3: Semantic query cache.** On `/query`, embed the question, cosine against a recent-queries set; if >0.97 similarity, return cached result. Massive cost win at scale. Files: `services/retrieval.py`.
- [ ] **BB4: Managed cloud offering (`bigrag.cloud`).** Multi-tenant hosted version with free trial API keys — the single biggest adoption lever. Needs P1-A4 (workspaces) + P2-E10 (quotas) first.
- [ ] **BB5: Streaming answer endpoint.** `POST /v1/answer` runs query + LLM with inline citations, streams via SSE. Pairs with BB2 for agentic flows.

---

## Remove / simplify

- [ ] **RM1: Drop `api_keys.permissions` column if P1-A1 isn't shipping this quarter** — unused today, confusing in schema diffs.
- [ ] **RM2: Drop `api_keys.active` column** or ship a deactivate endpoint; current delete-only flow makes the column dead weight.
- [ ] **RM3: Make the 50-webhook cap configurable** (`models/webhook.py:12`) or remove entirely — it's arbitrary.
- [ ] **RM4: Audit `sdks/rust/`.** If unmaintained, mark deprecated in the folder's README and remove from the main README's SDK list.
- [ ] **RM5: Remove `milvus_nprobe` config if P1-V2 doesn't land** — it only applies to IVF_FLAT, the single hardcoded index type; exposing a knob that depends on another unconfigurable knob is confusing.

---

## Execution checkpoint

After every two P0 tasks land, run the full test suite (`cd api && uv run pytest`) and the e2e suite (`cd e2e && uv run python run.py`). After all P0 tasks land, **stop**, surface progress, and ask the user which P1 cluster to pick up first — retrieval quality, SDK, observability, or multi-tenancy all make sense as standalone sub-plans.

