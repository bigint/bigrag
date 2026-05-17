# bigRAG — End-to-End Data-Structure & Algorithm Review

20 specialized review agents, dispatched in parallel across the entire codebase
(~72 kLOC: api / app / 3 SDKs / migrations). Each report below cites file:line.

**Totals: ~26 Critical, ~76 High, ~57 Medium, ~32 Low, ~12 Nit (≈203 findings).**

## At-a-glance

| # | Subsystem | C | H | M | L | N |
|---|---|---|---|---|---|---|
| 1 | Retrieval & vector store | 1 | 4 | 3 | 2 | 0 |
| 2 | Chat engine | 2 | 4 | 4 | 2 | 1 |
| 3 | Embedding pipeline | 2 | 4 | 2 | 2 | 0 |
| 4 | Document ingestion | 1 | 3 | 3 | 1 | 1 |
| 5 | Queue / jobs / worker | 2 | 3 | 4 | 3 | 1 |
| 6 | Pagination | 1 | 3 | 3 | 2 | 1 |
| 7 | Caching layer | 2 | 4 | 3 | 1 | 1 |
| 8 | Auth & RBAC | 0 | 3 | 3 | 1 | 0 |
| 9 | Security middleware | 1 | 5 | 0 | 0 | 2 |
| 10 | Crypto / tokens / URL / file | 0 | 1 | 2 | 2 | 1 |
| 11 | Connectors (Google Drive) | 2 | 3 | 4 | 2 | 0 |
| 12 | Event bus & SSE | 3 | 4 | 4 | 3 | 1 |
| 13 | Backup & restore | 3 | 5 | 3 | 2 | 0 |
| 14 | Webhooks | 1 | 5 | 2 | 1 | 1 |
| 15 | DB layer & migrations | 1 | 3 | 3 | 2 | 1 |
| 16 | Storage & uploads | 2 | 4 | 3 | 3 | 1 |
| 17 | Runtime settings | 2 | 3 | 3 | 1 | 1 |
| 18 | TypeScript SDK | 2 | 6 | 2 | 0 | 1 |
| 19 | Rust SDK | 1 | 5 | 3 | 3 | 0 |
| 20 | Python SDK + frontend hooks | 1 | 4 | 3 | 2 | 0 |

---

## TOP 25 BUGS TO FIX FIRST

Ranked by combination of severity, blast radius, and exploitability.

### 1. Hybrid search is broken — semantic always dominates
`api/bigrag/services/retrieval.py:451-459` & `vector_store/qdrant.py:452-453`
RRF receives unequal candidate lists (semantic up to top_k, keyword filtered from a 3×top_k scroll). Worse, keyword `scroll` returns in insertion order, not relevance, so true matches past the 3×top_k window are permanently invisible. Hybrid mode silently behaves like semantic mode.

### 2. Vector store backend swap races with in-flight queries
`api/bigrag/services/vector_store/__init__.py:130-143`
`replace_with` releases the swap lock before closing the old backend; a query that wakes between those two lines hits a half-closed backend → runtime error or silent corruption.

### 3. Instance OpenAI API key leaked via cache key
`api/bigrag/services/chat/provider.py:114`
Raw `api_key` used as a `dict` key in a module-level `_chat_clients`. Sits in heap for process lifetime; visible in any heap dump / `gc.get_objects()` / future repr.

### 4. Instance chat key escapes via admin-configured `chat_base_url`
`api/bigrag/services/chat/turn.py:71-77`
Recent SSRF fix only blocks user-supplied `provider_base_url`. An admin-set `chat_base_url` still forwards the instance key — a key-leak channel the prior fix missed.

### 5. Cursor pagination 500s the moment two rows share `created_at`
`api/bigrag/services/pagination.py:57,63`
`apply_cursor` compares the `uuid` column against a `str` literal → `operator does not exist: uuid < text`. Triggers as soon as two documents share a `created_at` timestamp (common on bulk imports).

### 6. Documents `order=asc` silently loses/duplicates rows at tie boundary
`api/bigrag/routers/documents.py:313`
ORDER BY tie-break is hardcoded `id.desc()` regardless of `order`; cursor predicate uses `id > cur_id` for ascending. Page boundaries hitting equal `created_at` skip or repeat rows.

### 7. Idempotency middleware has no single-flight — duplicate mutations
`api/bigrag/middleware/idempotency.py:117-128`
Cache miss → execute → cache write is not atomic. Two concurrent identical requests both miss, both run, last writer wins. The exact failure idempotency keys exist to prevent.

### 8. Embedding cache keyed without `input_type` — wrong vectors served
`api/bigrag/services/embedding_cache.py:18-19` & `queue_embedding.py:26-90`
Cohere/Voyage treat `search_document` vs `search_query` as different embedding spaces. Cache key omits `input_type`; queries silently get document-space vectors, degrading retrieval quality.

### 9. Sentinel `None` can be evicted, leaking SSE consumers forever
`api/bigrag/services/event_bus.py:179-185` + `161-177`
`_offer` drops oldest when full; the completion sentinel can be evicted, leaving `stream()` consumers blocked indefinitely on `queue.get()`. Combined with double-publication of the sentinel (local + Redis), the cleanup contract is unsound.

### 10. SSE subscribe-after-snapshot loses events
`api/bigrag/routers/admin_realtime.py:111-116`
Snapshot loaded → yielded → only THEN `event_bus.subscribe`. Any event between snapshot start and subscribe is dropped — hundreds of ms window per subscriber on cold DB.

### 11. Backup tables snapshotted at different points in time
`api/bigrag/services/backup/exporters.py:28`
Each table exported in its own session — no `REPEATABLE READ`. Active writer can leave `documents` and `document_chunks` in inconsistent state across the dump.

### 12. Backup `file_path` is a path-traversal vector
`api/bigrag/services/backup/exporters.py:123`
`temp_dir / "uploads" / doc.file_path` with no `..` / absolute-path guard. Compromised DB row writes outside the backup root.

### 13. Backup manifest has no HMAC / signature
`api/bigrag/services/backup/manifest.py` & `services/backup/jobs.py:143-164`
`manifest.json` and `checksums.json` are unsigned. An attacker with bucket write can flip `raw_uploads`, row counts, or `app_version` to mislead restore.

### 14. Cleanup deletes ACTIVE upload sessions (silent data loss)
`api/bigrag/services/cleanup.py:60-62`
`DELETE FROM upload_sessions WHERE updated_at < cutoff` has no `status` filter. Slow-uploading sessions with stale `updated_at` get hard-deleted (CASCADE to items).

### 15. Upload session lock held across all file I/O
`api/bigrag/routers/upload_sessions.py:401-590`
`SELECT FOR UPDATE` on the session row is held through `stream_upload_to_temp`, `validate_upload`, and `storage.put_stream`. All concurrent uploads to one session are serialized for the full wall-clock duration.

### 16. Concurrent dedup race produces duplicate document rows
`api/bigrag/routers/documents.py:235-246` & `_documents.py:215-223`
`SELECT WHERE content_hash` then `INSERT` with no `UNIQUE(collection_id, content_hash)`. Two identical uploads land both rows → duplicate vector-store entries, inflated counts.

### 17. Decrypted API keys cached in Redis as plaintext when crypto unconfigured
`api/bigrag/services/collection_cache.py:26-42` + `redis_cache.py` encode path
`_serialize` ships decrypted `embedding_api_key` etc.; `_encode_value` only Fernet-wraps when `crypto.is_configured()` is true. Master key not configured → third-party API keys sit unencrypted in Redis.

### 18. Tenant filter rejects multi-value `$in` arrays
`api/bigrag/services/tenant_enforcement.py:49`
`$in` branch requires `len == 1`. Any legitimate multi-tenant query (`tenant_id: {$in: ["a","b"]}`) is refused with `400 missing tenant filter`.

### 19. Scope path matcher accepts extra trailing segments
`api/bigrag/services/scopes.py:62-77`
`zip` terminates at pattern length without checking actual path is the same length. Pattern `POST /v1/collections/{name}/documents` matches `/v1/collections/foo/documents/batch/delete` — latent privilege escalation if scope-table ordering ever flips.

### 20. Collection-pinned key bypass via trailing-slash URL
`api/bigrag/services/collection_scope.py:7-15, 38-59`
Pinned-key guard checks `len(parts) == 3`. `PUT /v1/collections/` and `DELETE /v1/collections/` normalize to 2 segments — pinned-key restriction does not fire.

### 21. Webhook `(status, next_retry_at)` index missing — outbox poll degrades
`api/bigrag/db/models.py:567-570`
Only individual indexes on `status` and `webhook_id`. Polling query filters on status='pending' AND next_retry_at<=now ORDER BY created_at — full pending-partition scan as backlog grows.

### 22. Worker queue: stats endpoint triggers job recovery as side-effect
`api/bigrag/services/queue.py:216-219` + `queue_state.py:99`
Any caller polling `stats` re-runs `_recover_stuck_jobs` and re-enqueues. The dashboard or healthcheck causes N duplicate enqueues per poll for the same stuck job.

### 23. Worker queue: recovery LREM + enqueue is not atomic — double processing
`api/bigrag/services/queue.py:113-116` + `queue_state.py:99`
Recovery `LREM`s the job from PROCESSING and only then enqueues to dramatiq, with no transaction. A worker can pick up dramatiq message before the DB row is reset to `pending` → status overwrite + duplicate ingestion.

### 24. SSE `\r\n\r\n` block terminator never flushes events (TS SDK)
`sdks/typescript/src/sse.ts:58`
Parser splits on `\n` only. Behind any proxy that normalizes line endings (nginx/ALB/Cloudflare), the empty separator arrives as `"\r"` and `flush()` is never called — events buffer until close.

### 25. SSE multi-byte UTF-8 corrupted across chunk boundaries (Rust SDK)
`sdks/rust/src/sse.rs:111` + `resources/chat.rs:81` + `resources/admin.rs:814`
`String::from_utf8_lossy(&chunk)` per-chunk turns split continuation bytes into U+FFFD. Any non-ASCII text crossing a chunk boundary is permanently corrupted before JSON parse.

---

## CRITICAL findings — by subsystem

### Retrieval
- **vector_store/__init__.py:130-143** — backend swap closes old backends after releasing condition lock (race window).

### Chat
- **provider.py:114** — raw API key as dict key in `_chat_clients`.
- **turn.py:71-77** — instance chat key escapes through admin `chat_base_url` (recent fix incomplete).

### Embedding
- **queue_embedding.py:274-275** — unbounded `asyncio.gather` over all batches; no semaphore at fan-out layer.
- **embedding_cache.py:18-19** — `input_type` missing from cache key → query/document space contamination.

### Ingestion
- **ingestion.py:78-84** — char-split chunks' `char_end` computed from `len(part)` while text stores `part.strip()` → citation offsets wrong.

### Queue / jobs
- **queue.py:113-116** + **queue_state.py:99** — recovery LREM + enqueue not atomic → double processing.
- **queue.py:216-219** — `stats` property runs recovery as a side effect → repeated enqueues on every poll.

### Pagination
- **pagination.py:57,63** — `uuid` column compared to `str` literal → 500 at every tie-break.

### Caching
- **collection_cache.py:26-42** — decrypted API keys cached plaintext when crypto unconfigured.
- **retrieval.py:143** — `query_epoch:*` `INCR` keys have no TTL → unbounded Redis growth.

### Security middleware
- **idempotency.py:117-128** — no single-flight on cache miss → duplicate execution of mutating requests.

### Event bus & SSE
- **admin_realtime.py:111-116** — subscribe-after-snapshot TOCTOU (lost events).
- **event_bus.py:161-177** — `complete()` double-publishes sentinel (local + Redis).
- **event_bus.py:179-185** — `_offer` can evict completion sentinel under load (consumer never wakes).

### Connectors
- **google_drive_client.py:282-303** — no retry on 429/5xx; first rate-limit fails the entire sync.
- **google_drive_auth.py:206-231** — token-refresh stampede (no single-flight per account).

### Backup
- **exporters.py:28** — no `REPEATABLE READ` transaction; tables snapshotted at different times.
- **target.py:21** + **jobs.py:143-151** — `BackupUploadStats.objects` holds full upload list in memory.
- **jobs.py:28-41** — TOCTOU between active-job check and INSERT.

### Webhooks
- **webhook.py:108-113** — DNS-rebind window between registration validation and per-delivery pin.

### DB & migrations
- **alembic/versions/0018_audit_log_immutable.py:21-22** — `RULE DO INSTEAD NOTHING` breaks FK `ON DELETE SET NULL`; pre-0027 instances cannot delete users/api_keys; 0027 downgrade re-installs the bug.

### Storage / uploads
- **upload_sessions.py:407-413** — TOCTOU on `client_item_id` → 500 instead of idempotent 201.
- **_documents.py:200-219** — storage object written before DB commit → leaks on commit failure.

### Runtime settings
- **runtime_setting_specs.py:714-716** — `REGISTRY` assigned twice (copy-paste defect).
- **admin_settings.py:52-68** — `CredentialCheckError` not caught → 500 with traceback to admin client.

### TS SDK
- **core.ts:94** — no user-supplied AbortSignal → fetches uncancellable.
- **core.ts:106-108** — non-idempotent POST/PATCH retried on 5xx without checking whether idempotency key was sent.

### Rust SDK
- **sse.rs:111** — `from_utf8_lossy(&chunk)` per chunk corrupts multi-byte UTF-8 across chunk boundaries.

### Python SDK + frontend
- **use-sse-snapshot-query.ts:69-77** — both `addEventListener("error", …)` and `es.onerror` registered → error doubles `failureCount`, premature polling-fallback.

---

## HIGH findings — selected highlights by subsystem

### Retrieval
- `qdrant.py:452-453` — text_search `scroll` is insertion-ordered; over-fetch ×3 silently caps results.
- `retrieval.py:451-459` — hybrid RRF lists unequal length → semantic always wins.
- `qdrant.py:357-379` — `get_chunks` loads all chunks before slicing (page in DB, not in RAM).
- `routers/query.py:215-224` — N sequential `get_collection_or_404` before fan-out in multi-collection retrieve.

### Chat
- `provider.py:115-136` — DNS rebind on cached `OpenAI` clients (TTL never re-validated).
- `questions.py:255` — `finally: await client.close()` closes the SHARED cached client.
- `completion.py:91-101` — stream not closed on client-disconnect `return` path (resource leak).
- `formatting.py:13,21` — `_safe_chat_error` regex only catches `sk-` keys.

### Embedding
- `queue_embedding.py:82-86` + `embedding_cache.py:114-150` — no NaN/Inf guard on provider vectors.
- `embedding.py:44-49` — race on `_embed_semaphores` dict creation → concurrency limit doubled.
- `embedding.py:353-386` — Voyage embed has no 128-input batch split.
- `embedding_rate_limit.py:138-140` — TOCTOU on Redis `PTTL` then conditional `SET`.

### Ingestion
- `queue_conversion.py:220` + `conversion.py:231` — file fully loaded into memory then re-written to temp.
- `documents.py:235-246` / `_documents.py:215-223` — concurrent identical upload races create duplicates.
- `_documents.py:215-223` — storage orphan on second commit failure.

### Queue
- `queue_state.py:16-18` — lease active-TTL margin 120 s; 60-second renew cycle leaves false-recovery window.
- `queue.py:374` + `:508` — backoff has no jitter → simultaneous retry storm.
- `queue_state.py:84-104` — `recover_stuck_jobs` issues N sequential TTLs (no pipeline).

### Pagination
- `documents.py:313` — tie-break direction mismatch for `order=asc` → data loss/dup at boundary.
- Index gap: `collections`, `users`, `api_keys`, `webhooks`, `backup_jobs` all paginated, none indexed `(created_at DESC, id DESC)`.
- Cursor + offset accepted together silently — `offset=1000000` works.

### Caching
- `collection_cache.py:62-78` — no stampede guard; TTL expiry burst all hit DB simultaneously.
- `collection_cache.py:15-16` — `collection:{name}` key has no namespace / encoding; colons in name collide.
- `redis_cache.py:63-65` — `delete_pattern` sequential `DEL` per key (auth invalidation O(N) sync).
- `embedding_cache.py:76-110` — two DB sessions per `get_many` (hit + `last_hit_at`).

### Auth & RBAC
- `tenant_enforcement.py:49` — `$in` only accepts single value → multi-tenant queries rejected.
- `scopes.py:62-77` — `_path_matches` accepts extra trailing segments.
- `collection_scope.py:7-15` — trailing-slash `PUT/DELETE /v1/collections/` bypass pinned-key guard.

### Security middleware
- `idempotency.py:155-172` — crash between handler exec and Redis write → key never recorded.
- `csrf.py:18-33` — no Bearer-token exemption in origin check.
- `cors.py:37-40` — reflects `Access-Control-Request-Headers` verbatim with no allowlist/sanitization.
- `maintenance.py:13-21` — no admin-path bypass; lock cannot be lifted via API once active.
- `_principal.py:46-47` — `"ip:unknown"` collision when proxy strips X-Forwarded-For.

### Crypto / URL / file
- `url_security.py:239-281,373-391` — double DNS resolve in pin path → rebind window.

### Connectors
- `sync.py:131-133` — all `download_tasks` pre-launched (memory + leaked temp files on crash).
- `sources.py:103-114` — `create_sync_job` lacks `source.status != 'syncing'` guard → duplicate sync rows.
- `sync.py:64-67`, `sources.py:116` — crash leaves source `"syncing"` forever; scheduler then skips it.

### Event bus & SSE
- `event_bus.py:103-104,116-118` — `_dispatch` iterates live subscribers list while modifications possible same-turn.
- `use-sse-snapshot-query.ts:83,233` — `MAX_RECONNECT_ATTEMPTS` exhaustion leaves stream permanently dead; new mounts get the dead entry.
- `event_bus.py:42`, `admin_realtime.py:45,70` — no `id:` or `retry:` SSE fields → no Last-Event-ID replay, no client retry hint.

### Backup
- `exporters.py:70-83` + `vector_store/{qdrant,turbopuffer}.py` — `export_collection_points` materializes whole collection.
- `target.py:76-85` — local SHA-256 before upload; no server-side `ChecksumSHA256` validation.
- `jobs.py:177-198` — drain loops have no timeout; stuck ingestion holds maintenance lock until 12 h TTL.

### Webhooks
- `webhook.py:44-48` — `verify_signature(timestamp=None)` is accepted → replay protection optional.
- `webhook.py:410,444` — replay/test issue fresh `X-BigRAG-Delivery` UUID, breaking consumer dedup.
- `webhook.py:287-296` — outbox loop is sequential; one slow endpoint blocks all 25 items.
- `webhook.py:175` — `_get_webhooks` selects all active webhooks per event; missing index on `webhooks.active`.

### DB
- `alembic/versions/0021_collection_vector_store_provider.py:23-51` — `ADD COLUMN NOT NULL` + UPDATE in same tx → long AccessExclusiveLock.
- `alembic/versions/0024_api_key_mcp_predicate_indexes.py` — index lacks `id` for cursor tie-break.
- `admin_access.py:146-147` — unbounded `offset` on `access_log` (high-volume table).

### Storage
- `routers/upload_sessions.py:401-590` — session row lock held across all I/O.
- `routers/upload_sessions.py:630-652` — `cancel_upload_session` not `FOR UPDATE` → file completes after cancel.
- `_documents.py:197` — `collection_name` flows into storage key with no slug validation.

### Runtime settings
- `runtime_settings.py:24-26, 247-259` — in-process 5 s cache → multi-replica drift on security settings.
- `routers/admin_settings.py:51-53` — `update_settings` commits before `apply` → DB/live divergence.
- `runtime_settings.py:247-259` — async RMW race on `_cached_values`.

### TS SDK
- `sse.ts:44-49` — `retry:` / `id:` fields silently dropped.
- `sse.ts:58` — `\r\n\r\n` events never flushed (proxy-normalized streams).
- `collections.ts:85-87` — response body not consumed before throw → leaked connection.
- `core.ts:87` — no jitter (thundering herd).
- `core.ts:111-114` — `Retry-After` header ignored.
- `files.ts:16-18` — `readFile` buffers whole file in memory.

### Rust SDK
- `core.rs:184` — POST/PATCH retried on 5xx unconditionally.
- `core.rs:193-197` + `error.rs:129` — `Retry-After` discarded.
- `files.rs:60-65` — `FileInput::Path` fully buffers; `Stream` works but `Path` doesn't.
- `sse.rs:123` — `wake_by_ref()` busy-loop on heartbeat-only chunks (100% CPU).
- `sse.rs:30-31` — `to_string()` + clone on every block boundary.

### Python SDK + frontend
- `sdks/python/src/bigrag/_core.py:25-55,186` — files fully buffered; `_rewind_files` is a no-op stub.
- `sdks/python/src/bigrag/_core.py:126-129` — 429 `Retry-After` ignored.
- `sdks/python/src/bigrag/_sse.py:21-31` — single-line parser; multi-line `data:` and `retry:` dropped.
- `sdks/python/src/bigrag/_core.py:106` — exponent off by one; no jitter.

---

## MEDIUM / LOW / Nit findings

Comprehensive list lives in each agent's detailed report; the highlights worth keeping in mind:

### Common patterns across many subsystems
- **No jitter on backoff** anywhere — Python SDK, Rust SDK, TS SDK, queue worker, webhook delivery.
- **No `Retry-After` honored** anywhere — all three SDKs, queue worker, webhook delivery.
- **Cache stampedes unguarded** — `collection_cache`, `embedding_cache` queries, query-result cache.
- **No structured error subclasses by HTTP status** — TS SDK, Python SDK (`403 PermissionDeniedError` missing).
- **TOCTOU on `client_item_id` / `content_hash` / `idempotency-key` / `connector source`** — recurring pattern; each one needs a unique partial index + `ON CONFLICT`.
- **DB sessions opened per-iteration** in several places (`embedding_cache.get_many` hit path, `admin_realtime` per snapshot, backup table loop).
- **No tenant/scope namespace** in cache keys, event-bus subscriber keys, idempotency keys, cursor tokens.

### Less-critical but worth filing tickets for
- Pagination cursor unauthenticated and unsigned (`pagination.py:15-18`).
- Frontend `useCollection` no `staleTime` (refetch on every focus).
- Access tokens stored plaintext in `connector_accounts` table.
- `Webhook.active` has no index.
- `update_sync_progress` commits per file (write amplification).
- `event_token` not deleted after validate (`getdel` instead of `get`).
- `WebhookDelivery` connection drained inside `__aexit__` rather than explicit `aclose()` (semaphore held longer than necessary).

---

## Recommended fix order

1. **Block release** — fixes that prevent silent corruption / privilege escalation: #1-6, #17-20, #22-23.
2. **Operational stability** — #7, #8, #9, #10, #14, #21, #24.
3. **Security hardening** — #3, #4, #11-13, plus crypto / URL-pin medium findings.
4. **Performance & resource** — embedding/cache/connector/SDK retry & jitter findings.
5. **Long-tail correctness** — medium/low/nit findings; group by file when fixing.

Each section's findings cite file:line — implement in that order or fan out to teammates by file.
