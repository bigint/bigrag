# bigRAG End-to-End Cleanup & Refactor Plan

> Status: pre-release, no backward-compat needed; the codebase is safe to break in pursuit of clarity. Project policy: NO comments / docstrings in `api/bigrag/`, `sdks/typescript/src/`, `app/`, `website/` (only functional pragmas).

Synthesized from 18 parallel audits of every slice of the monorepo (admin/core/connectors/chat/retrieval/jobs/runtime/misc/db services; SDKs Py+TS+Rust; app routes/features/hooks/components; website; e2e/infra; deps; top-level docs; alembic).

The plan is split into:

1. **Single migration to "look everything simple"** — one shipping PR (or branch) that lands all the structural moves below in one commit per slice and the alembic collapse as the final step.
2. **Per-slice cleanup checklists** — exact files, lines, and actions.
3. **Single Alembic migration plan** — wipes history, collapses 30 → 1.
4. **Bug-fix queue** — correctness/security/perf items broken out from refactor noise.
5. **Quick wins to ship first.**

---

## 1. The "single migration" execution plan

Execute as one branch `cleanup/2026-05`. Each numbered step is one commit; commit titles are conventional commits per `~/.claude/CLAUDE.md`.

> Order is chosen so each step works after the one before — and ends with the Alembic collapse so reviewers see a single new migration file.

1. **chore: drop dead modules and back-compat shims**
   - delete `api/bigrag/services/google_drive.py` (facade only `connector_registry.py` uses)
   - delete `api/bigrag/services/connector_core.py` (only `list_sync_jobs` consumed externally → import from `connectors.sources` directly)
   - delete `api/bigrag/services/connectors/__init__.py` content (treat as flat namespace)
   - delete `api/bigrag/services/jobs/__init__.py` (empty file)
   - delete `api/bigrag/utils.py` (inline `safe_create_task` into `services/retrieval.py`)
   - delete `api/bigrag/models/common.py` (move `StatusResponse` to `models/__init__.py`)
   - delete `api/bigrag/services/queue.py` dead exports + `IngestionQueue.flush_collection`, `start`, `_ocr_scanned_pdf`, `_promote_due_retries`, `_FLUSH_LUA`, `_ENQUEUE_LUA`
   - delete `api/bigrag/services/queue_state.py` legacy enqueue/retry/Lua paths (keep only lease/epoch/recovery + `flush_collection_jobs` + `queue_stats` + `IngestionCancelledError`)
   - delete `api/bigrag/services/connectors/google_drive_sources.py:86-101 create_google_sync_job` (dead)
   - delete `api/bigrag/services/connectors/google_drive_types.py:81-82` type aliases (`RemoteDriveFile`, `DownloadedDriveFile`)
   - delete `api/bigrag/services/webhook.py` `_listen`, `start`, `stop`, module-level `webhook_dispatcher` singleton, `_ = response.status_code`
   - delete `api/bigrag/services/url_security.py` `validate_outbound_url_sync`, `validate_chat_base_url_sync`, `pin_webhook_url`, `validate_webhook_url`
   - delete `api/bigrag/services/event_bus.py:39 IngestionEvent.to_sse`, `:292 EventBus.stream`
   - delete `api/bigrag/services/access_log.py:321 flush_access_logs`, `services/audit.py:167 flush_audit_logs`
   - delete `api/bigrag/services/retrieval.py:111-112 fuse_results`, `:329-330 _vector_store_label`, `:323-326` hasattr guard
   - delete `api/bigrag/services/vector_store/__init__.py:190-198 _client`, `client` attr, `_sync_client`; `:272-289 payload_fields` param
   - delete `api/bigrag/services/vector_store/base.py:12-20 DEFAULT_SEARCH_PAYLOAD_FIELDS`
   - delete `api/bigrag/services/conversion.py:151-162 _conversion_worker`, `:225-253 convert_document_isolated` (bytes form)
   - delete `api/bigrag/services/storage.py:352-358 init_storage`
   - delete `api/bigrag/services/embedding.py:441-456` LRU footprint (rewrite eviction to await aclose())
   - delete unused runtime specs: `runtime_setting_specs.py:348 storage_signed_url_ttl_seconds`, `:673 progress_snapshot_retention_days`, `:703 audit_log_retention_days`, `:183 upload_session_upload_concurrency`
   - delete `runtime_settings.py:49 invalidate_runtime_settings_cache`
   - delete `e2e/stubs/fake_gdrive/` entirely + `e2e/conftest.py:636-689 gdrive_oauth_helper`, host_base fixtures (`:100-103`, `:112-115`, `:124-127`), `:572-579 webhook_sink_url`, `:38 FAKE_OPENAI_BASE` and `:60-74 __all__`
   - delete `e2e/tests/api/test_connectors.py:439` skipped placeholder + `e2e/Makefile:5 fake-gdrive` entry
   - delete `scripts/strip-route-tree-comments.mjs` (no references)
   - delete `app/src/features/chat/chat-store.ts:14,55 startNewChat`
   - delete `app/src/types/bigrag.ts` barrel
   - delete `website/app/500/page.tsx` (duplicate of error.tsx)
   - delete `website/content/docs/openrag-gap-analysis.mdx` (815-line strategy memo) + drop the closing callout in `comparison.mdx:58-60`
   - delete `DSA_REVIEW.md` (one-off audit snapshot; convert remaining items to issues)
   - delete **`sdks/rust/`** entirely (6.6k LoC, no publish workflow, no consumers, examples-only) + `.github/workflows/ci.yml:82-95 rust-sdk-check` + `website/content/docs/sdks/rust.mdx`

2. **refactor: collapse façade services and rename modules**
   - rename `api/bigrag/middleware/_principal.py` → `middleware/principal.py`
   - rename `api/bigrag/db/models.py Session` → `UserSession` (drop `as DbSession` aliases in 3 importers)
   - merge `api/bigrag/services/collection_cache.py` + `collection_config.py` + `collection_scope.py` → `services/collection.py`
   - merge `api/bigrag/services/connectors/scheduler.py` + `progress.py` → `services/connectors/sync.py`
   - move `api/bigrag/services/{client_ip,event_tokens,pagination}.py` → `services/utils/{client_ip,event_tokens,pagination}.py`

3. **refactor(api): split god-files along audit-defined seams**
   - `db/models.py` (751) → `db/models/{auth,instance,collection,document,connector,webhook,observability,preference}.py` (re-export from `db/models/__init__.py`)
   - `main.py` (403) → `main.py` + `app_factory/{lifespan,exception_handlers,routers}.py`
   - `mcp_server.py` (376) → `mcp/{_tools,_unscoped,_scoped,cli}.py`
   - `routers/documents.py` (847) → `documents.py` + `documents_batch.py` + `documents_global.py`
   - `routers/collections.py` (752) → `collections.py` + `collection_events.py` (+ `_collections.py` for shared `_collection_response`)
   - `routers/upload_sessions.py` (679) → `upload_sessions.py` + `_upload_sessions.py` (+ extract per-stage handlers)
   - `routers/query.py` (518) → `query.py` + `vectors.py` + `analytics.py`
   - `routers/admin_realtime.py` (561) → keep router; move 30-line SSE framework to `services/sse_stream.py`
   - `services/retrieval.py` (593) → `retrieval/{__init__,cache,rerank,fusion,log}.py`
   - `services/embedding.py` (581) → `embedding/{base,openai,cohere,voyage,registry}.py` + `embedding/_models.json` (constants)
   - `services/vector_store/__init__.py` (386) → thin re-export + `facade.py` + `_util.py`
   - `services/vector_store/qdrant.py` (546) → keep backend; extract `_to_qdrant_filter`/`_combine_filters` → `qdrant_filter.py`
   - `services/storage.py` (403) → `storage/{base,local,s3,factory}.py`
   - `services/webhook.py` (495) → `webhook/{dispatcher,http,payload}.py`
   - `services/url_security.py` (411) → `url_security/{validate,pin,transport}.py`
   - `services/queue.py` + `queue_conversion.py` + `queue_embedding.py` + slimmed `queue_state.py` → `services/ingestion/{pipeline,convert,embed,state}.py`; rename `services/jobs/` → `services/dramatiq/`, fold `worker.py` into it
   - `services/runtime_setting_specs.py` (714) → `runtime_setting_specs/{security,ingestion,queue,storage,backups,vector_store,search,chat,webhooks,retention}.py` (one per `SettingGroup`), with `__init__.SETTING_SPECS` aggregation
   - `services/runtime_settings.py` + `runtime_settings_apply.py` → `runtime_settings/{registry,store,apply}.py`
   - `services/connectors/sync.py` (543) → `sync_runner.py` + `sync_document.py`
   - `services/connectors/sources.py` (377) → `sources.py` + `sync_jobs.py`
   - `services/connectors/google_drive_client.py` (359) → `google_drive_client.py` + `google_drive_oauth_client.py`
   - `services/connectors/google_drive_auth.py` (291) → `google_drive_auth.py` + `google_drive_tokens.py`
   - `services/chat/questions.py` (322) → `questions/{api,generation}.py`
   - `services/chat/turn.py` (309) → `turn/{prepare,credentials}.py`
   - `services/backup/` 7-file → 4-file (target+manifest merged, constants→exporters, filesystem→exporters)

4. **refactor(api): extract shared helpers, kill duplication**
   - Promote one canonical `uuid_or_404(label)` in `routers/__init__.py`; replace 8+ inline copies
   - Add `services/pagination.py::decode_cursor_or_400(cursor)` + `paginate(session, stmt, *, sort_col, id_col, limit, offset, cursor, count_stmt=None)`; sweep 5 admin + 4 user-facing cursor blocks
   - Move `services/credential_check.py::verify_or_422(...)` + replace 6+ try/except → 422 wrappers across `embedding_presets.py`, `preferences.py`, `collections.py`
   - Move `_callback_url` / `_route_or_404` / `_mcp_permissions_filter` to `services/connector_registry.py` / `services/auth.py`
   - Add `services/bootstrap.py::init_runtime(values, *, with_event_bus=True)` and call from both `main.py` lifespan and `services/jobs/runtime.py` (dedupe ~150 lines of duplicated worker init)
   - Add `services/_log_queue.py::LogQueue(name, table, batch_max, queue_max)` and refactor both `access_log.py` and `audit.py`
   - Add `services/origin.py::is_origin_allowed(origin, request, cors_origins)` and call from both `middleware/cors.py` and `middleware/csrf.py`
   - Promote `crypto._FERNET_PREFIX` to `crypto.FERNET_PREFIX` + expose `crypto.is_encrypted(value)`; sweep `services/chat/turn.py:200` and `routers/preferences.py:81`
   - Move `decrypt_preferences` from `routers/preferences.py` into `services/preferences.py` (kills `services → routers` import inversion in `services/chat/turn.py:14`)
   - Move `_documents.py` symbols imported by `services/connectors/*` into `services/` (kill `routers → services → routers` cycle)
   - Extract chat-credential-fallback loop (in `provider.py` `_complete_model`/`_stream_model` and `questions.py:209-256 _generate_questions_text`) into a single `_try_credentials(prepared, action)` helper; unify exception type to `ServerError`
   - Replace string-prefix coupling between `chat/provider.py:_provider_error` and `_is_saved_key_auth_error` with a typed marker on `UpstreamError`

5. **refactor(app): extract bloated routes into features/**
   - Move full pages out of `app/src/routes/`: `_dashboard.api-keys.tsx` → `features/api-keys/api-keys-page.tsx`; `_dashboard.models.tsx` → `features/models/models-page.tsx`; `_dashboard.collections.$name.settings.tsx` → `features/collections/settings-tab.tsx` (split into RetrievalDefaultsCard / EmbeddingKeyCard / AllowedFileTypesCard / DangerZoneCard); search/index/layout/collections.index/auth login+setup/root index — see `12-app-routes.md`
   - Add `features/auth/use-auth-gate.ts` to collapse 4 redirect hooks
   - Add `features/collections/use-collection-name.ts`
   - Add `components/status/ApiUnreachable.tsx` and replace 2 byte-identical copies
   - Replace `routes/_dashboard.collections.$name.connectors.index.tsx` + `routes/index.tsx` spinner-then-redirect with TanStack `beforeLoad` + `throw redirect(...)`

6. **refactor(app): split heavy features**
   - `collections/documents-tab.tsx` (820) → `documents-tab.tsx` + `documents-upload-dropzone.tsx` + `documents-upload-session-panel.tsx` + `documents-bulk-actions.tsx`
   - `overview/overview-page.tsx` (665) → `overview-metrics.tsx` + `overview-access-center.tsx` + `overview-readiness.tsx` + `overview-queue.tsx`
   - `mcp/mcp-page.tsx` (650) → extract dialogs and `mcp-snippets.ts` + `mcp-tool-catalog.ts`
   - `chat/chat-messages.tsx` (650) → `chat-markdown.tsx` + `chat-source-card.tsx` + `chat-assistant-message.tsx`
   - `settings/tabs/instance-settings-tab.tsx` (588) → `instance-settings-panel.tsx` + `instance-setting-field.tsx`
   - `connectors/connectors-page.tsx` (442) → extract `google-connector-panel.tsx` + `planned-connector-panel.tsx` + `provider-header.tsx`
   - `chat/chat-page.tsx` (394) → introduce `use-chat-conversation.ts` hook; move LoadingState/NoCollectionsState → `chat-empty-states.tsx`
   - Fold `google-drive-panel.utils.ts` and `google-drive-panel-hooks.ts` into `google-drive-progress.ts`

7. **refactor(app): shared modules**
   - Split `hooks/use-sse-snapshot-query.ts` (253) → `lib/sse-stream-pool.ts` + 80-line hook + `lib/use-latest-ref.ts`
   - Merge `components/ui/page-container.tsx` + `page-shell.tsx` + `page-header.tsx` → `components/ui/page.tsx` exporting `Page.{Container,Shell,Header}`
   - Add `lib/query-factory.ts::createInvalidatingMutation(...)` + sweep `use-{api-keys,mcp-servers,embedding-presets,webhooks,backups}.ts`
   - Add `lib/api.ts::apiUrlWithParams(base, params)` and `compactRecord` (sweep three callsites)
   - Collapse hand-rolled admin types in `app/src/types/bigrag-api/admin.ts` onto SDK re-exports
   - Add `lib/form.ts::defineFormSchema<TValues,TBody>(...)` + `useTypedForm(schema, options)` and sweep the 6 `*-form-state.ts` files

8. **refactor(sdk): split admin mega-files + add missing endpoints**
   - Split `sdks/python/.../resources/admin.py` (605) and `sdks/typescript/.../resources/admin.ts` (503) into `admin/{settings,backups,realtime,users,api_keys,access,audit,connectors,embedding_presets,mcp_servers}` sub-modules
   - Strip 206 Python docstring lines + 1174 Rust `///` lines (... if Rust SDK kept; otherwise N/A)
   - Add `embedding-presets/test`, `vector-storage/overview`, `chat/question-suggestions`, `collections/.../events/token` to Python and TS SDKs

9. **fix: behavioral and security follow-ups** (see Bug Queue below for exact items)

10. **chore: docs sync** (collapse README env table, fix line 342 split, decide on configuration.mdx as source of truth, drop `next-env.d.ts` postbuild script as appropriate)

11. **chore(alembic): collapse 30 migrations into single 0001_initial_schema.py** (see §3)

12. **chore: gitignore + minor hygiene**
   - Add `.ruff_cache/` to `.gitignore` (optional)
   - Lift shared docker-compose env to YAML anchors
   - Replace `app/docker-entrypoint.sh` sed gymnastics with `envsubst`
   - Composite action `.github/actions/setup-node-pnpm/` for ci.yml + e2e.yml install dedup

---

## 2. Per-slice cleanup checklists

The per-slice details live in `/tmp/bigrag-audit/{01..19}*.md`. The bullet headers above reference them; each section is one PR checklist row.

---

## 3. Single Alembic migration — concrete plan

Execute exactly as the final step of the cleanup branch. Pre-release ⇒ no data ⇒ no backfills.

### Inventory of the 30 migrations being collapsed

(see `/tmp/bigrag-audit/10-alembic-plan.md` for full per-file summary)

### Drops to preserve (do NOT recreate)
- `collections.redact_pii`, `collections.moderation_enabled` (from 0004)
- `api_keys.rate_limits` JSONB (from 0008)
- table `s3_ingest_jobs` (from 0009)
- tables `chat_conversations`, `chat_messages` (from 0023; only `chat_question_suggestions` from 0026 stays)
- Legacy RULES `no_audit_update`/`no_audit_delete` on `audit_log` (0027 superseded 0018)
- Old `id` `server_default=gen_random_uuid()` on the 19 tables (0030 removed it; consolidated migration must NOT emit `server_default` on those ids — Python-side `default=uuid7` via `UUIDpk` in `db/base.py`)

### Bootstrap impact
None. `api/bigrag/db/bootstrap.py` runs `command.upgrade(cfg, "head")`. No revision IDs hardcoded anywhere outside the migration files themselves. `api/bigrag/services/backup/jobs.py:183` will start recording `db_revision="0001"` (informational only).

### Recipe
```bash
# 1. Wipe all migration files
rm api/alembic/versions/0001_*.py api/alembic/versions/0002_*.py ... api/alembic/versions/0030_*.py
rm -rf api/alembic/versions/__pycache__

# 2. Wipe dev DB (no prod data)
dropdb --if-exists bigrag_dev && createdb bigrag_dev

# 3. Autogenerate from db/models.py (env.py imports them)
cd api && uv run alembic revision --autogenerate -m "initial schema"

# 4. Rename file → 0001_initial_schema.py; force revision="0001", down_revision=None

# 5. Manually append the 0027 audit_log triggers at end of upgrade(), AFTER audit_log is created (see 10-alembic-plan.md for exact SQL with DROP TRIGGER IF EXISTS prefixes)
```

### Raw SQL to append (does not autogenerate)
See `10-alembic-plan.md` — two PL/pgSQL functions `audit_log_block_content_modifications` + `audit_log_block_delete`, two triggers `audit_log_no_content_update` + `audit_log_no_delete`. Always prefix each `CREATE TRIGGER` with `DROP TRIGGER IF EXISTS … ON audit_log;`.

### Verification (drift check — MUST be empty)
```bash
dropdb bigrag_dev && createdb bigrag_dev
cd api && uv run alembic upgrade head
uv run alembic history          # → one row: 0001 (head)
uv run alembic revision --autogenerate -m drift_check
# Inspect upgrade()/downgrade() — both should be only `pass`
rm api/alembic/versions/*_drift_check.py

dropdb bigrag_dev && createdb bigrag_dev
cd api && uv run alembic upgrade head
psql bigrag_dev -c "\dt"
psql bigrag_dev -c "\d audit_log"
psql bigrag_dev -c "\df audit_log_block*"
psql bigrag_dev -c "\d users"
psql bigrag_dev -c "SELECT version_num FROM alembic_version;"
cd api && uv run python -c "import asyncio; from bigrag.db.bootstrap import run_migrations; asyncio.run(run_migrations())"
cd api && uv run pytest
```

### Risks
- Existing dev/CI databases still holding `alembic_version='0030'` will refuse to upgrade — drop+recreate, or `DELETE FROM alembic_version; alembic stamp 0001`.
- `pgcrypto` extension no longer needed for DDL — only old (deleted) migrations referenced `gen_random_uuid()`. Confirm no other usage.
- Autogenerate quirks to eyeball before commit: literal_column emission for Index expressions; check-constraint names (`users_role_check`, `collections_vector_store_provider_check`, `embedding_presets_provider_check`, `chat_question_suggestions_questions_array_check`); JSONB `server_default=sa.text("'{}'::jsonb")` formatting.

---

## 4. Bug-fix queue (correctness / security / performance)

### High (security / correctness)
- **`services/chat/questions.py:62-73`** — `generate_question_suggestions` lacks the guard added by commit `a74960b4` in `services/chat/turn.py:79-87`: when admin saves a custom `chat_base_url` and the user has no `openai_key`, the **instance `BIGRAG_CHAT_API_KEY` is silently shipped to the third-party endpoint**. Factor the guard into a shared helper called from both `_prepare_chat_turn` and `generate_question_suggestions`.
- **`detail=str(exc)` anti-pattern in ~25 routes** (`admin_api_keys.py:85,123,195`, `upload_sessions.py:325,402`, `documents.py:226,484,605`, `connectors.py:105,107,109,130,152,260,262,264,300,317,346,194`, `evaluation.py:110`, `webhooks.py:55,160,284`, `admin_access.py:136`, `admin_users.py:62`, `admin_backups.py:55,102`, `admin_audit.py:66`, `collections.py:191,321,704`) — same root cause as the recent `UpstreamError`/`ServerError` fix. Most wrap `ValueError`/`ValidationError`/SDK exceptions whose `__str__` can carry upstream provider messages, DSN fragments, library internals. **Add a `public_message` slot to `BigRAGError`**, update `main.py:248` ValidationError handler to honor it, then convert all 25 callsites to classify and emit a curated `detail` (log raw `exc` server-side via `get_logger.warning(..., error=repr(exc))`).
- `services/embedding_cache.py:18` — cache key missing `api_key`/`base_url` tag → two OpenAI-compatible providers serving same model name silently corrupt cached vectors. Add to cache identity.
- `services/url_security.py:115-121` — allowlisted URL bypasses HTTPS requirement entirely. Keep HTTPS enforcement unless allowlisted target is private/loopback.
- `services/connectors/google_drive_auth.py:218-253` — multi-process refresh race: in-process `asyncio.Lock` only serializes within one event loop; second worker silently overwrites token. Use `SELECT … FOR UPDATE`.
- `services/connectors/google_drive_auth.py:35 _REFRESH_LOCKS` — unbounded dict per `account_id`. Memory leak. Use `WeakValueDictionary` or LRU.
- `services/connectors/google_drive_client.py:130 userinfo`, `:119` token errors — `raise … (response.text)` leaks raw Google response body (bubbles via `routers/connectors.py:194 quote(str(exc))` into OAuth callback redirect URL). Extract known-safe `error`/`error_description`.
- `services/vector_store/__init__.py:167,186` — `provider_health()` and `health_check()` write `f"{exc.__class__.__name__}: {exc}"` into JSON served by `routers/admin_vector_storage.py`. Qdrant/Turbopuffer client exceptions can embed URLs, ports, auth headers. Categorize like `routers/health.py:_categorize_dependency_error`.
- `routers/_documents.py:286-291` (`get_document_with_collection`) → `documents.py:818-826` (`/v1/documents/{document_id}`) — global document lookup runs unconditionally, only checks `assert_collection_pin_matches` AFTER fetching. Leaks existence/timing for documents in collections a scoped key can't see. Move pinned-collection enforcement into the query (`Document.collection_id == pinned_collection_id`).
- `routers/admin_realtime.py:80` — admin SSE error frames include `str(exc)` from snapshot loaders. Apply `_safe_chat_error`-style redaction.
- `routers/documents.py:128`, `_documents.py:254`, `documents.py:516`, `services/connectors/sync.py:415` — `doc.error_message = f"enqueue failed: {exc.__class__.__name__}: {exc}"` persists raw Dramatiq/Redis errors that are returned in `DocumentResponse.error_message`. Store categorized short message + log full exception.
- `services/connectors/google_drive_auth.py:138`, `services/connectors/accounts.py:169` — `account.oauth_state != state` not constant-time. Use `hmac.compare_digest`.
- `services/queue.py:465-552` exception handler leaks `str(e)` into `Document.error_message` + `IngestionEvent.message` + webhook payloads. Mirror commit `be85296c`.
- `services/connectors/sync.py:294 str(exc)` of arbitrary exception stored in `source.last_error` (returned via API). Sanitize.
- `routers/documents.py:436-451 delete_document` + `routers/collections.py:732-735 truncate_collection` + `:615-619 delete_collection` — delete vectors BEFORE committing DB delete. Reorder: row delete → commit → vector + storage cleanup.
- `routers/admin_users.py:34-45 _ensure_admin_role_can_change` — race on demotion can leave zero admins (concurrent demotions both read `len(admin_ids)==2`).
- `routers/admin_backups.py:111` — DB committed before broker enqueue; if Dramatiq down, backup job stuck `pending` forever.
- `middleware/auth.py:138` — cache key under `matched_hash or api_key.key_hash` means old-master-key clients never warm cache. `_cache_set` for each `key_hash in key_hashes`.
- `middleware/auth.py:126` — `_touch_api_key_last_used(last_used_at=api_key.last_used_at)` only on DB path; cache-hit branch passes `None` → 60-sec gate skipped, always Redis SETNX. Pass cached value through principal.
- `services/connectors/sync.py:43-60` — `with_for_update()` held for entire sync (minutes). Blocks router reads. Release after status flip or use advisory lock.
- `services/connectors/sources.py:103-119` — `create_sync_job` race: `SELECT FOR UPDATE … skip_locked` returning `None` raises "syncing"; fast click 404s. Check `existing` first.
- TENANT SCOPING: `connector_core/accounts.py` use `user_id` only — `ConnectorAccount → Collection` binding never enforced tenant. User in tenant A can bind to tenant B's collection.
- `app/src/routes/_auth.login.tsx:58` — `window.location.assign(from)` after login does full reload, loses React Query cache. Use `navigate({ to: from, replace: true })`.
- `app/src/hooks/use-auth.ts:73-78,86-91` — logout doesn't tear down EventSource pool; revoked-cookie reconnect storms server with 401s. Expose `closeAllStreams()` and call in `useLogout` onSuccess.
- SDKs **Python `_core.py:112-154`** and **Rust `core.rs:69-103`** retry POST/PUT/PATCH on 5xx/429 without `Idempotency-Key`. Generate UUID4 per mutating call, mirror TS.
- SDKs `admin.{py,rs}::realtime.custom(path, params)` — accepts arbitrary `path`. Assert `path.startswith("/v1/admin/realtime/")`.

### Medium
- `services/jobs/actors.py` — all actors set `max_retries=0`. `run_google_drive_sync`, `process_webhook_outbox`, `run_backup`, `run_cleanup` lose messages on raise.
- `services/jobs/actors.py:36-40 enqueue_ingestion_job` — no idempotency / dedupe. SET NX `bigrag:ingestion:inflight:<doc>` lock.
- `services/jobs/runtime.py:28-40` — double-checked init wrong: `with _thread_lock` returns early on `_initialized` but never sets it under lock. Drop `_thread_lock`, only use `asyncio.Lock`.
- `services/queue.py:478-486 IngestionCancelledError` — no `_fanout_webhook_event` for cancelled events; failed/complete do. Subscribers never learn about cancels.
- `services/queue.py:537-538` — DLQ uses `LPUSH` + `LTRIM 0 999`, but two readers see different DLQs. Pick one (dramatiq XQ + structured `dead_letters` table).
- `services/queue.py:155-182 enqueue` — `queue_size(INGESTION_QUEUE)` returns only ready length; depth check ignores delayed+retry → `queue_max_depth` cap leaky under retry storms.
- `services/runtime_settings.py:262-275` — multi-worker stale-cache: settings change in one worker silently doesn't apply elsewhere for 5s. Redis pub/sub invalidation or per-request middleware.
- `routers/admin_settings.py:51-60` & `:102-113` — DB committed then `apply_prepared_runtime_settings` swaps backends; if apply raises, no compensating rollback. Probe storage **before** commit.
- `services/maintenance.py:37-55` — `acquire_backup_lock` cleanup-DELETE lost on rollback. Use `INSERT … ON CONFLICT (name) DO UPDATE WHERE expires_at <= now()`.
- `services/collection_cache.py:73,96` — `_fill_locks.pop` inside finally → cache stampede on race. Use long-lived locks, never pop.
- `services/collection_cache.py:90-92` — `random.randint(0, ttl//10)` raises `ValueError` if `ttl<10`. Use `max(1, ttl//10)`.
- `services/event_tokens.py:39-42` — token without `|` treated as legacy → vacuously matches all collections. Remove legacy fallback.
- `services/event_bus.py:194,215` — discards task reference from `ensure_future`; tasks may be GC'd. Use `create_task` + stash in `self._pending`.
- `services/event_bus.py:114 self._completed` grows unboundedly. Cap.
- `services/audit.py:182-212 record()` — if `_audit_queue is None`, logs and drops silently. Block until flusher up, or raise.
- `services/webhook.py:131` — new `WebhookDispatcher()` per actor call defeats per-webhook `Semaphore(5)`. Module-level dict or process-wide singleton.
- `services/webhook.py:99-124 _post_pinned` calls `response.aclose()` before returning — `response.text/json()` would fail. Currently safe only because callers read `.status_code`. Remove.
- `services/url_security.py:97-102` — IPv6 from `getaddrinfo` returned without brackets; `url.copy_with(host=ipv6)` may emit malformed URL. Wrap in `[...]`.
- `vector_store/qdrant.py:144-159` — exception heuristic by `str(e).lower()` substring. Restrict to qdrant-client structured types.
- `vector_store/qdrant.py:198` — `"exists" in str(exc).lower()` matches unrelated errors. Use structured error.
- `vector_store/turbopuffer.py:213-229 get_chunks` — always asks `limit:{total:10000}`; chunks beyond silently dropped. Implement `["id","Gt", last_id]` pagination.
- `vector_store/__init__.py:130-143 replace_with` — closes old backends inside `_swapping=True` lock; long stall during hot-swap. Close outside.
- `services/embedding.py:493-494` — Voyage LRU eviction doesn't `await aclose()` → httpx leak.
- `services/embedding.py:399-422` — Voyage `_API_URL` hardcoded; bypasses SSRF pinning. Pin against `api.voyageai.com`.
- `app/src/features/chat/chat-page.tsx:330` — `onResume={handleRegenerate}` is misleading UX (Play icon silently re-asks previous prompt). Either implement real resume or remove `onResume`.
- `app/src/features/chat/chat-store.ts:24-28` — module-top side effect removes `localStorage.bigrag-chat`. Guard with `__migrated_v1` flag or delete.
- `app/src/hooks/use-documents.ts:154-175` — one rejection in `Promise.all` skips `/complete`, orphans session. Use `Promise.allSettled`.
- Python SDK `_sse.py:13-45` — drops the `event:` field for collection events; callers can't distinguish progress/heartbeat/error. Return `{"event": event, "data": ...}`.
- Rust SDK `sse.rs:122-135 SseStream::poll_next` — returns `Pending` after zero-frame chunk without re-poll/wake. Stalls on partial UTF-8.
- Rust SDK `core.rs:250-254 do_request` — always calls `response.json::<T>()` on 2xx; 204 → serde error.
- TS SDK `core.ts:289` — `AbortSignal.timeout(this._client.timeout)` for SSE kills long-lived streams at 120s default. Separate stream timeout.

### Low / hygiene
- `mcp_servers.py:36, 41, 57, 74` — `Field(description=...)` prose; OpenAPI keeps these but they double as comments. Decide policy.
- `services/access_log.py:336-393 AccessLogMiddleware` — `metadata.setdefault("route", route)` overwrites with `None` when missing. `route` also stored as column → duplicative.
- `db/engine.py:46-47` — silently clamps `pool_min > pool_max`. Log warning.
- `db/models.py:185` — `idx_documents_collection_hash` non-partial composite on nullable column. Make partial `WHERE content_hash IS NOT NULL`.
- `db/models.py:156` — drop `idx_documents_collection_id` (covered by composite); `:697 idx_access_log_actor` (covered by `idx_access_log_actor_created_at`).
- `main.py:284-300` — hoist `import traceback` from inside catch-all handler.
- `config.py:124` — silently `flat.pop("vector_store_provider", None)` — log instead.
- `embedding_rate_limit.py:33-44` — `header_value` fallback iterating `Mapping` is dead in practice.
- `services/access_log.py:155` `include_total` runs full-table `COUNT(*)`.
- `services/admin_audit.py:38-89` lacks `_window_filter`/window cap that `admin_access.py` enforces.
- `routes/_dashboard.collections.$name.documents.index.tsx:34` — canonicalisation collisions; extract `canonicalSearch()`.
- `app/src/features/...` (`document-detail-route.tsx:169`, `instance-settings-tab.tsx:113-117`, `chat-messages.tsx:423`) — native `confirm`/`prompt` instead of `ConfirmDialog` / Modal+Textarea.
- e2e test files: ~600 LoC of module docstrings + section dividers (lists in `16-e2e-infra.md`).

### Performance
- **`routers/collections.py:429-434 reembed_collection`** — N+1 UPDATE per document inside Python `for` loop. Replace with `sa.update(Document).where(Document.id.in_(doc_ids)).values(status='pending', error_message=None)` (single round-trip).
- `services/collection_cache.py:110-111 invalidate_for_preset` — `redis_cache.delete()` per name. Pipeline or use `MGET`/`UNLINK`.
- `services/chat/questions.py:182-195 _sample_chunks` — per-document `vector_store.get_chunks(...)` (bounded to 6 but each a network hop). Add `get_chunks_for_documents(doc_ids, per_doc=4)`.
- `services/retrieval.py:81 _keyword_score` — compiles regex per term per result; `pat.search(text_lower)` unbounded against chunk text. Precompile once per query, truncate very long chunks.
- `services/chat/provider.py:25-27 _chat_clients` — global dict keyed by `(sha256(api_key), base_url)` with 300s TTL but no upper bound / LRU eviction. Add max-size LRU like `services/embedding.py:_MODELS_MAX`.
- `routers/documents.py:151` / `_documents.py:208` — sync `Path.open("rb")` on event loop; mixing sync/async file handles susceptible to NFS stat stalls.
- `services/webhook.py:268` / `collections.py:399-405` — `webhook._handle_event` calls `_get_webhooks()` on every event with no caching — busy ingestion stream re-issues `SELECT * FROM webhooks WHERE active` per event. Cache for 1-5s.
- `services/retrieval.py:274-317 _log_query` — fresh session per call + `SELECT Collection.id` per query when `collection_id` not pre-resolved. Pass it down.
- `routers/query.py:159-183 _results_with_document_filenames` — fresh session per concurrent task in `batch_query`'s `Semaphore(8)`. Thread request session.
- `services/embedding.py` — per-provider `embed` duplicates `truncate → batch → asyncio.gather → _embed_single`. Extract mixin helper.
- `vector_store/qdrant.py:345-401 get_chunks` — for `offset=99000, limit=10` pulls 99010 chunks per page. Use cursor `offset=` with `chunk_index` payload index.
- `services/mcp_http.py:55-69 _client()` — new `httpx.AsyncClient` + `ASGITransport` per tool call. Cache per-app.
- `app/src/hooks/use-sse-snapshot-query.ts:188-250` — every filter change tears down/reopens EventSource. Hash path or accept stable `pathKey`.
- `app/src/features/chat/chat-page.tsx:73-86` — 9 separate `useChatStore((s) => s.x)` subscriptions → 9 renders per change. `useShallow` once.
- `app/src/features/overview/overview-page.tsx:84-86` — `queueItems`/`services` rebuilt each render. `useMemo`.
- `services/queue_embedding.py:283-291` — `Semaphore(8)` hard-coded; should be runtime setting.
- `services/queue_conversion.py:223-228` — per-chunk `asyncio.to_thread(fh.write, chunk)` — one thread hop per chunk. Drain once.

---

## 5. Quick wins to ship first (1-2 days, low risk)

In rough cost-vs-impact order:

1. **Single Alembic migration collapse** (the headliner — collapses 30 files → 1). Drop+recreate dev DB after merge.
2. **Delete the Rust SDK** + Rust CI job + Rust docs page (6.6k LoC).
3. **Delete the dead modules in step 1 of the execution plan** (1k+ LoC across `google_drive.py`, `connector_core.py`, queue/queue_state legacy, vector_store `_client/payload_fields`, runtime spec orphans, gdrive e2e stub, `openrag-gap-analysis.mdx`, `DSA_REVIEW.md`, `app/500/page.tsx`, etc.).
4. **Strip Python+Rust SDK docstrings** (~1380 lines) to match the no-comments policy already enforced in `api/bigrag/`/`app/src/`.
5. **Strip e2e test module docstrings + section dividers** (~600 LoC of decoration).
6. **Fix bug-queue "High" items** — most urgent ones first: (a) `chat/questions.py` parity-fix with commit `a74960b4`; (b) `BigRAGError.public_message` + sweep ~25 `detail=str(exc)` callsites; (c) `embedding_cache._model_key` add base/api-key fingerprint; (d) `url_security` allowlist HTTPS bypass; (e) gdrive refresh races + `_REFRESH_LOCKS` leak + raw `response.text` leaks; (f) vector-then-DB delete ordering (`delete_document`/`delete_collection`/`truncate_collection`); (g) last-admin race; (h) login full-reload + logout EventSource teardown; (i) Python and Rust SDK idempotency keys.
7. **Promote canonical helpers** (`uuid_or_404`, `decode_cursor_or_400`, `paginate`, `verify_or_422`, `is_origin_allowed`, `init_runtime`, `LogQueue`) — frees the file splits to be mechanical.
8. **Then** the larger structural file splits in steps 3, 6 of the execution plan.

---

## 6. Files this plan touches (rough count)

- **Delete**: ~25 files (incl. all 30 alembic migrations + entire Rust SDK + `openrag-gap-analysis.mdx` + `DSA_REVIEW.md` + dead stubs + dead helpers)
- **Rename**: ~5 (`Session` → `UserSession`, `_principal.py` → `principal.py`, `services/jobs/` → `services/dramatiq/`, etc.)
- **Split**: ~25 (god-files and bloated routes)
- **Merge**: ~10 (collection_cache+config+scope, connectors scheduler+progress→sync, page-container+shell+header, backup constants/filesystem→exporters, ...)
- **New shared helpers**: ~12 modules (`services/pagination.paginate`, `services/credential_check.verify_or_422`, `services/bootstrap.init_runtime`, `services/origin.is_origin_allowed`, `services/_log_queue.LogQueue`, `lib/query-factory`, `lib/sse-stream-pool`, `lib/form.defineFormSchema`, `components/status/ApiUnreachable`, `features/auth/use-auth-gate`, `features/collections/use-collection-name`, `components/ui/page`)
- **New single Alembic migration**: 1 file `0001_initial_schema.py`

After this branch lands the repo loses ~20-25 files and the public surface (routes, SDK methods, public service exports) becomes more navigable. No public API behaviour changes other than tightened security and corrected ordering bugs.
