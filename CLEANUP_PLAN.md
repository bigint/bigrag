# bigRAG Cleanup & Refactor Plan — v2 (current-state audit)

> Status: pre-release, no backward-compat. Policy: NO comments / docstrings in `api/bigrag/`, `sdks/typescript/src/`, `app/`, `website/` (only functional pragmas: `# type: ignore`, `# noqa`, `// @ts-nocheck` on generated files). Python SDK is the only exception — see §3.
>
> Synthesized from 10 parallel end-to-end audits run against the current state (after the recent refactor commits collapsed alembic 30→1, split db/models, retrieval, embedding, webhook, main.py, extracted documents_batch/collection_events/_upload_sessions, dropped Rust SDK, dropped fake_gdrive, plus ~20 security/correctness fixes).
>
> v1 (the prior CLEANUP_PLAN.md) is ~70% done. This file lists only what's STILL pending plus NEW findings the v1 audit missed.

---

## 0. Where things stand

- ✅ Alembic 30 → single `0001_initial_schema.py` landed (`514d25fb`).
- ✅ Rust SDK + CI job + Rust docs page deleted (`ffc49854`).
- ✅ `services/{retrieval,embedding,webhook}.py` split into packages.
- ✅ `db/models.py` (751) → `db/models/` package by domain.
- ✅ `main.py` (403) → `main.py` + `app_factory/{lifespan,exception_handlers,routers}.py`.
- ✅ Routers extracted: `documents_batch.py`, `collection_events.py`, `_upload_sessions.py`.
- ✅ `safe_error_detail` sweep across ~25 callsites.
- ✅ ~20 High/Medium bugs from v1 queue fixed (see §6 triage).
- ✅ `BigRAGError.public_message` + sanitisation honored in exception handlers.

Still pending or newly identified: everything in this document.

---

## 1. Execution sequence (one commit per step)

Use branch `cleanup/2026-05-v2`. Conventional-commit titles per `~/.claude/CLAUDE.md`. Each step is one commit; commit + push after each (per memory).

1. **chore: drop NEW dead modules and symbols** (§2)
2. **chore(sdk-py): strip generated docstring noise** (§3)
3. **refactor(api): promote canonical helpers + sweep callsites** (§4)
4. **refactor(api): rename `_principal.py` → `principal.py` and `Session` → `UserSession`** (§5.1)
5. **refactor(api): break `routers → services → routers` cycles** (§5.2)
6. **refactor(api): split remaining oversized routers** (§5.3)
7. **refactor(api): split remaining oversized services** (§5.4)
8. **refactor(api): extract `services/sse_stream.py` + `services/health.py` + `services/analytics.py` + `services/collections.py` (move logic out of routers)** (§5.5)
9. **refactor(api): split `mcp_server.py` (376) into `mcp/` package** (§5.6)
10. **refactor(app): page-shell merge, route → features moves, hook consolidation** (§7)
11. **refactor(sdk): split admin mega-files + add missing endpoints + idempotency parity** (§8)
12. **fix: remaining High/Medium bug queue items** (§6)
13. **chore(api): plug remaining tenant-scoping gaps** (§4.6)
14. **chore(infra): docker-compose anchors, gitignore, composite CI action** (§9)
15. **chore(alembic): move check constraints into `__table_args__` so autogen drift = 0** (§10)
16. **chore(docs): README + AGENTS + STYLEGUIDE sync, delete `CLEANUP_PLAN.md` and `MIGRATION_PLAN.md`** (§11)

Step 15 is the second "look-everything-simple" migration: it makes `alembic revision --autogenerate` produce an empty diff against the current `0001_initial_schema.py`.

---

## 2. NEW dead code to delete

### api/bigrag/services/

- `services/queue.py:17-39, 41-64, 140-141, 316` — module-level Redis key constants (`QUEUE_KEY`, `PROCESSING_KEY`, `DEAD_LETTER_KEY`, `RETRY_KEY`, `STATS_KEY`, `LEASE_KEY_PREFIX`, `COLLECTION_EPOCH_KEY_PREFIX`, `DOCUMENT_EPOCH_KEY_PREFIX`), aliases (`_LEASE_*`, `_EMBEDDING_TIMEOUT_SECONDS`, `_PERMANENT_ERRORS`, `_PDF_OCR_*`, `_docling_result_text`, `_embed_with_cache`, `_delete_document_vectors_after_failure`, `_lease_key`, `_collection_epoch_key`, `_document_epoch_key`), `__all__`, `IngestionQueue._FLUSH_LUA = ... / _ENQUEUE_LUA = ...`, and the class-attr `_PLAIN_TEXT_EXTS = queue_conversion.PLAIN_TEXT_EXTS`. All in-file only; no external importer.
- `services/queue_state.py:21-65, 149-180, 167-180, 19` — `ENQUEUE_LUA`, `PROMOTE_RETRIES_LUA`, `RETRY_PROMOTION_LIMIT`, `enqueue_job`, `schedule_retry_job`, `promote_due_retries` — no consumers after `queue.py` slim-down. After delete, file shrinks 238 → ~110 LoC.
- `services/webhook/dispatcher.py:65-71` — `WebhookDispatcher.start`/`stop` never wired in lifespan; singleton only used for `deliver_once`/`deliver_test`.
- `services/retrieval/__init__.py:36` — `"RetrievalOutcome"` in `__all__` has no external importer.
- `services/vector_store/__init__.py:100-107` — `VectorStore.supports_text_search` property is dead (only `supports_text_search_for` is consumed).
- `services/conversion.py:151-162` `_conversion_worker` + `:8 from multiprocessing.connection import Connection` — no caller.
- `services/cleanup.py:18-27` `cleanup_old_data` (the loop variant) — only `cleanup_old_data_once` is wired into the dramatiq actor.
- `services/runtime_settings.py:55` `set_runtime_settings_cache` — only used inside same module by `update_settings`/`reset_settings`; not in public surface.
- `services/url_security.py:151,171,204,217,348` — `validate_outbound_url_sync`, `validate_outbound_url` (async), `validate_chat_base_url_sync`, `validate_embedding_base_url` (async), `pin_webhook_url` — no callers (v1 listed the sync trio; the two async dupes are NEW).
- `services/connector_core.py:66-78` `run_due_syncs_logged` — dead helper inside an already-doomed module; module slated for deletion.
- `services/google_drive.py` (entire 94-LoC façade) — only `connector_registry.py` imports it; fold into `connector_registry.py` then delete.
- `services/jobs/__init__.py`, `services/connectors/__init__.py`, `services/__init__.py` — empty / only `from __future__ import annotations`; can be deleted (PEP-420).
- `services/utils.py` (api/bigrag/utils.py — 22 LoC) — only `safe_create_task`; inline into `services/retrieval/__init__.py` and delete.

**Do NOT delete** (v1 said dead, but is not):
- `services/connectors/google_drive_types.py:81-82` — `RemoteDriveFile`, `DownloadedDriveFile` ARE used as type aliases in `google_drive_client.py` and `google_drive_sync.py`. v1 was wrong.

### api/bigrag/routers/

- `routers/health.py:185-186` — `_categorize_provider_error(exc)` is a one-line wrapper; inline `_categorize_dependency_error` at line 137.
- `routers/admin_realtime.py:33` — `TERMINAL_DOCUMENT_STATUSES` duplicates `routers/documents_progress.py:8`; import the canonical one.
- `routers/connectors.py:407-411` — `uuid_or_400` defined locally, called once at `:392` and the return value is discarded.

### api/bigrag/db, models, config, etc.

- `db/models/observability.py:55,56` — `QueryLog.collection_id` FK + `idx_query_log_collection_id` index. Every reader uses `QueryLog.collection_name`. Drop both, or migrate readers onto the FK and remove the denormalised name.
- `db/models/observability.py:100, 103, 105` — `idx_access_log_actor`, `idx_access_log_action`, `idx_access_log_collection` — each is covered by a composite `(*, created_at)` sibling.
- `db/models/document.py:16` `idx_documents_collection_id` — covered by composites starting with `collection_id`.
- `db/models/instance.py:30` `MaintenanceLock.owner_id` — declared `sa.Uuid` with no FK while `services/maintenance.py:63` treats it as a user id. Add `sa.ForeignKey("users.id", ondelete="SET NULL")` or drop.
- `config.py:52 embedding_concurrency`, `:53 qdrant_search_ef`, `:61 conversion_pdf_ocr_enabled` — shadowed by runtime_setting_specs of the same key; the `Settings` field is never read.
- `config.py:122-123` — silent `flat.pop("vector_store_provider", None)` + `flat.pop("run_migrations", None)`.
- `models/__init__.py` — empty barrel; either delete or move `StatusResponse` from `models/common.py:6` here.
- `models/common.py` — 1-symbol module; after moving `StatusResponse` to `models/__init__.py`, delete.
- `models/webhook.py:12 MAX_WEBHOOKS = 50` — no importer.
- `models/webhook.py:8-19 validate_outbound_webhook_url`/`resolve_and_validate_url` — single-call indirection; inline into `routers/webhooks.py:54` and drop the module-level re-export.

### app/

- `app/src/features/chat/chat-store.ts:14, 55 startNewChat` — only `clearMessages` is consumed.
- `app/src/features/chat/chat-store.ts:24-28` — module-top one-shot `localStorage.removeItem("bigrag-chat")` with no version guard.
- `app/src/components/status/status-page.tsx` (164 LoC) — not wired into the route tree.
- `app/src/routes/_dashboard.collections.tsx` and `_dashboard.collections.$name.documents.tsx` — 6-LoC pure `<Outlet />` shells; TanStack Router file-based routing generates these implicitly.

### sdks/

- `sdks/python/src/bigrag/__init__.py:24-45,73-93` — root-level re-exports of every `Admin*Resource`; users get them via `client.admin.users.*` — dead public surface.
- `sdks/python/src/bigrag/_client.py:118-127` — `chat_create` / `chat_stream` duplicate `client.chat.create()` / `client.chat.stream()`.
- `sdks/python/src/bigrag/_client.py:105-109` — `get_analytics` shim; move onto `CollectionsResource.analytics()` (mirror TS).
- `sdks/python/src/bigrag/_client.py:144-272 CollectionClient` — 17 one-line delegates around `client.documents.*`. Delete the class; callers do `client.documents.upload(name, ...)`.
- `sdks/typescript/src/types.ts` — single-line re-export of `types/index.ts`; collapse to one path.
- `sdks/typescript/src/types/documents.ts:55-57, 77-79` — `BatchStatusBody`, `BatchDeleteBody` — never imported.
- `sdks/typescript/src/types/admin.ts:268-273` — re-export block duplicates `types/index.ts` barrel.

### e2e/

- `e2e/conftest.py:56-69 __all__` — `FAKE_OPENAI_BASE`, `WEBHOOK_SINK_BASE`, `DOCUMENTS_DIR`, `fixture_path` are unused outside conftest. `ADMIN_*` consumed only by `tests/api/test_auth.py` → move to `tests/_helpers.py`.
- `e2e/conftest.py:88-91 webhook_sink_base` fixture — no consumers; `webhook_sink.url(label)` is what tests actually use.
- `e2e/conftest.py:42-47` — `FAKE_OPENAI_INTERNAL_BASE` / `WEBHOOK_SINK_INTERNAL_BASE` env overrides never set. Hard-code.
- `e2e/tests/_helpers.py:39-40` `fixture_path()` — no callers.
- `e2e/tests/_helpers.py:19 DOCUMENTS_DIR` — only re-exported by conftest. Inline into `read_fixture`.

### website/ and root docs

- README.md:74 — Mermaid `SDK([TS / Python / Rust SDK])` — drop "Rust" (post-`ffc49854`).
- `website/content/docs/index.mdx:10` — `"…TypeScript / Python / Rust SDKs…"` — drop "Rust".
- README.md:327-328 — broken Markdown table split.
- CalVer skew: 9 places hard-code `2026.4.30`, others use `2026.5.7`. See §9.
- Once cleanup-branch lands: delete `CLEANUP_PLAN.md` (this file) and `MIGRATION_PLAN.md`.

### infra / scripts

- `app/package.json:32 serve` + the `start` script (line 11) — production uses nginx; no consumer.
- `app/package.json:24 clsx` — used only inside `lib/cn.ts`; `tailwind-merge` alone suffices.
- `e2e/package.json:14 tsx` — no `tsx` invocations.
- `api/pyproject.toml:20 pydantic[email]` — `EmailStr`/`email_validator` not imported anywhere.
- `api/pyproject.toml:30 botocore` — transitive of `boto3`.
- `bigrag.toml:82-83` — `upload_session_upload_concurrency` example for a setting that no longer exists.
- `bigrag.toml:27, 53, 86` — TOML examples for keys that are now runtime-managed (drift trap).
- `.pre-commit-config.yaml:27 exclude` — references `.next-dev/` which doesn't exist.
- `.dockerignore:2` — `docs/` doesn't exist.
- `.gitignore` — duplicates with `e2e/.gitignore` (`.pytest_cache/`, `.venv/`); missing `.ruff_cache/`.
- `.github/ISSUE_TEMPLATE/config.yml:4,7` — points to `github.com/bigint/bigrag`; canonical is `yoginth/bigrag`.
- `.github/ISSUE_TEMPLATE/bug_report.yml:38` — placeholder `"0.1.x or commit SHA"` while CalVer is in use.

---

## 3. Strip generated docstring noise (Python SDK)

The "no comments / docstrings" policy is fully enforced in `api/bigrag/`, `sdks/typescript/src/`, `app/src/`, `website/`. The **Python SDK is the sole hold-out**: 232 docstring lines + 23 `# section` comments.

Strip:
- `_client.py` (35), `resources/admin.py` (43), `resources/documents.py` (20), `resources/auth.py` (16), `resources/connectors.py` (13), `resources/collections.py` (13), `resources/webhooks.py` (12), `_core.py` (12), `_errors.py` (12), `resources/chat.py` (9), `resources/query.py` (7), `resources/vectors.py` (6), `_files.py` (5), `_sse.py` (5), `resources/evaluations.py` (3) + 25 one-liner module headers in `types/*.py`.

Keep only Pydantic `Field(description=...)` strings (load-bearing for OpenAPI) and required Alembic file-header docstrings.

(If the user prefers to keep Python SDK docstrings for IDE hover — that's the v1 default. Decide once.)

---

## 4. Helper promotions + duplication kills

### 4.1 Canonical helpers to promote

Promote into `api/bigrag/routers/__init__.py` (or a sibling `routers/_helpers.py`) and sweep all callsites:

- `uuid_or_404(value, label)` — canonical lives at `routers/documents_uploads.py:41`. Inline copies at: `_documents.py:273-274`, `connectors.py:407-411`, `admin_users.py:131-134, 195-198`, `embedding_presets.py:144-147, 171-174, 238-241`, `mcp_servers.py:214-217, 279-282, 318-321`, `admin_api_keys.py:174-175, 238-239, 274-275`, `admin_backups.py:85-88` (400 form), `admin_audit.py:55-58` (400 form, "actor_id"), `admin_access.py:115-118` (400 form, "actor_id"). 13+ rewrites.
- `decode_cursor_or_400(cursor)` → into `services/pagination.py`. Callers: `collections.py:181-187`, `documents.py:213-225`, `admin_users.py:58-65`, `admin_api_keys.py:81-88`, `admin_audit.py:62-69`, `admin_access.py:132-139`, `admin_backups.py:51-58`, `webhooks.py:158-165, 284-291`. 10 rewrites.
- `ensure_embedding_or_400(collection)` — wraps `get_embedding_model_for` + the 6-line "embedding model unavailable" 400 block. Callers: `documents.py:69-74, 331-338`, `documents_batch.py:208-215`, `upload_sessions.py:84-91, 164-172`, `query.py:79-85`, `evaluation.py:108-115`. 7 rewrites.
- `verify_or_422(provider, api_key, base_url, model=None, *, message=None)` → into `services/credential_check.py`. Callers: `collections.py:50-61`, `embedding_presets.py:79-87, 126-134, 151-159, 188-197`, `preferences.py:58-67`. 6 rewrites.
- `is_mcp_key(key)` + `_mcp_permissions_filter()` → into `services/auth.py` or `services/scopes.py`. Verbatim duplicates in `admin_api_keys.py:34-35, 66-69` and `mcp_servers.py:26-27, 128-132`.
- `connector_callback_url(request, route)` + `connector_runtime_or_404(slug)` → into `services/connector_registry.py`. Duplicate copies in `routers/connectors.py:35-49` and `routers/admin_connectors.py:16-30`. Note: connectors.py version index-errors on `request.client[0]`; admin_connectors.py version uses `request.client.host` — adopt the safer form.
- `is_origin_allowed(origin, request, cors_origins)` → into `services/origin.py`. Duplicates in `middleware/csrf.py:48-54` and `middleware/cors.py:61-77`.
- `crypto.FERNET_PREFIX` + `crypto.is_encrypted(value)` — promote out of private `crypto._FERNET_PREFIX`. Sweep `services/chat/turn.py:200, 211`, `routers/preferences.py:81, 113`.
- `init_runtime(values, *, with_event_bus=True)` → into `services/bootstrap.py`. Called from `app_factory/lifespan.py:52-72` and `services/jobs/runtime.py:52-78`. ~150 LoC of duplicated worker init.
- `LogQueue(name, table, batch_max, queue_max)` → into `services/_log_queue.py`. Refactor `services/access_log.py` + `services/audit.py` onto it. Kills duplicate `_uuid_or_none` helpers (`audit.py:27`, `access_log.py:60`).
- `retry_with_backoff(fn, *, retriable_statuses=…, max_attempts=…, base_delay=…)` → into `services/http_retry.py`. Sweep `services/connectors/google_drive_client.py:58-73, 289-318` and `services/vector_store/qdrant.py:122-160`.

### 4.2 Late-import hoists (cycle smells)

- `routers/collections.py:306, 618, 664` — hoist `from bigrag.services.embedding import get_embedding_model`, `from bigrag.services.storage import get_storage` to module top.
- `routers/query.py:454-464` — hoist `redis_cache, session_factory, sa, QueryLog` to top.
- `routers/webhooks.py:374-376` — hoist `datetime`, `orjson` to top.
- `routers/health.py:68, 124` — hoist `from bigrag.db.models import Collection, EmbeddingPreset` and `from bigrag.services.embedding import get_embedding_model` to top.

### 4.3 Cross-layer duplication (app/)

- **4 auth-redirect hooks** (`routes/index.tsx:72-93`, `layouts/dashboard-layout.tsx:110-135`, `routes/_auth.login.tsx:37-42`, `routes/_auth.setup.tsx:21-27`) → `features/auth/use-auth-gate.ts`.
- **3 "API unreachable" cards** (`layouts/dashboard-layout.tsx:137-149`, `routes/index.tsx:38-54`, `routes/_auth.login.tsx:74-94`) → `components/status/ApiUnreachable.tsx`.
- **9 `decodeURIComponent(rawName)` decoders** in collection routes → `features/collections/use-collection-name.ts`.
- **2 whoami "bearer test" flows** (`routes/_dashboard.api-keys.tsx:81-97`, `features/mcp/mcp-page.tsx:268-281`) → `lib/test-api-key.ts::testApiKey(plaintext)`.
- **Confirm-delete-mutation pattern** in 5 features → `hooks/use-delete-confirm.ts`.
- **Tanstack-form boilerplate** in 12 forms → `lib/form.ts::defineFormSchema({defaultValues, validate, onSubmit})` returning a pre-wired form + `<FormErrors form={form}>` component.
- **10 `useMutation + qc.invalidateQueries(...)` shapes** in `use-{api-keys,auth,backups,collections,documents,embedding-presets,google-drive,instance-settings,mcp-servers,webhooks}.ts` → `lib/query-factory.ts::createInvalidatingMutation(...)`.
- **`<Spinner size="lg">` centered loading** in 5 places → `<CenteredSpinner size>` or move into `Spinner`.
- **Two skip-to-content links** (root + dashboard layout) — pick one.
- **`statusVariant: Record<...>` maps** in 3 features → `lib/status-variants.ts`.
- **`formatPercent` / `formatMs`** inline in `overview-page.tsx:356-361` and `access-logs-page.tsx:75,80` → into `lib/format.ts`.
- **Merge** `components/ui/page-container.tsx` + `page-shell.tsx` + `page-header.tsx` → `components/ui/page.tsx` exporting `Page.{Container,Shell,Header}`. Sweep 14 importers.

### 4.4 Cross-layer duplication (api ↔ sdk ↔ app)

- `app/src/types/bigrag-api/admin.ts` + `settings.ts` re-implement types already in `sdks/typescript/src/types/`. Collapse to re-exports from `@bigrag/client` (like `chat.ts` already does).
- **SSE parser duplication**: `sdks/python/src/bigrag/_sse.py` drops `event:` field; `sdks/python/src/bigrag/resources/chat.py:_parse_frame` keeps it; `sdks/python/src/bigrag/resources/admin.py:_pop_sse_frame` is a third copy. Consolidate to one parser that always returns `{event, data}`.
- **Chat-credential-fallback loop** in `services/chat/provider.py::_complete_model`/`_stream_model` and `services/chat/questions.py:209-256 _generate_questions_text` → single `_try_credentials(prepared, action)` helper; unify exception type to `ServerError`.

### 4.5 Helper hot-spots (api/)

- `services/queue.py:269-299 _emit` is forwarded into `queue_conversion.py` + `queue_embedding.py` ~18 times, each repeating `collection_name=job.collection_name`. Bind via `emit_for(job).progress(step, status, msg, fraction, **detail)`.
- `services/connectors/sources.py:254, 283, 308` — 3 sequential `await source_for_user(... not_found_message=...)` calls; `@requires_source` decorator or `_resolve_source(...)` helper.
- `services/retrieval/__init__.py:80-82, 136-137, 171-172` — 3 `except VectorStoreFeatureError as exc: raise ValidationError(str(exc)) from exc` envelopes → `with _backend_call():` ctx manager.
- `services/runtime_settings.py:224-226, 240-242` — identical `_snapshot_runtime_values(rows)` lambda.
- `services/storage.py::LocalStorage._safe_path` + `S3Storage._key` — promote to `services/storage/_key_validation.py::validate_storage_key`.
- `services/connectors/google_drive_client.py:208-225` — replace `warnings.warn(...)` with `logger.warning(...)`.

### 4.6 Tenant-scoping gaps to plug

Add `enforce_collection_pin(user, collection_name)` helper in `routers/__init__.py` and sweep:

- `routers/documents.py:251-266 get_document`, `:269-311 delete_document`, `:314-396 reprocess_document`, `:399-424 get_document_chunks`, `:427-443 download_document_file`, `:449-458 get_document_global`, `:461-480 get_document_chunks_global`.
- `routers/documents_batch.py:287-353` — `batch_get_status`, `batch_get_documents`, `batch_delete_documents`.
- `routers/query.py:439-516 collection_analytics`.
- `routers/usage.py:43-153 get_usage` — pinned API key currently gets global usage.
- `routers/health.py:254-335 platform_stats` — same.
- `routers/collections.py:163-208, 456-466, 469-507, 510-589, 592-632, 635-677` — all CRUD bypasses pin enforcement; only `evaluation.py:103-104` does it.
- `routers/upload_sessions.py` — every handler scopes by `user_id` but never enforces `assert_collection_matches_pin`.

Plus: connectors do NOT carry tenant. `services/connectors/accounts.py:79-89, 127, 181` key by `user_id` only — cross-tenant binding is possible. Add `tenant_id` to `ConnectorAccount`/`ConnectorSource` (alembic), constrain Collection lookups to caller's tenant.

---

## 5. Refactor / structural moves

### 5.1 Renames (mechanical)

- `api/bigrag/middleware/_principal.py` → `principal.py` (only importer: `middleware/idempotency.py:8`).
- `api/bigrag/db/models/auth.py::Session` → `UserSession`. Drop the `as DbSession` aliases at `routers/auth.py:11`, `routers/admin_users.py:10`, `middleware/auth.py:14`.
- `api/bigrag/services/_retrieval_filters.py` → `services/retrieval/filters.py` (move into the package its only consumers live in).
- `api/bigrag/services/connector_registry.py` → `services/connectors/registry.py` (one connector namespace).
- `api/bigrag/db/models/document.py` — split `ChatQuestionSuggestion` → `db/models/chat.py`; `UploadSession`/`UploadSessionItem` → `db/models/upload.py`.
- `api/bigrag/models/auth.py::VALID_RESOURCES, VALID_ACTIONS` → `services/scopes.py` (pydantic file shouldn't own scope vocabulary).
- `api/bigrag/services/jobs/` → `services/dramatiq/`; fold `bigrag/worker.py` into `services/dramatiq/cli.py`.

### 5.2 Break `routers → services → routers` cycles

Move from `routers/_documents.py` → `services/documents.py`:
- `SUPPORTED_EXTENSIONS`, `prepare_document_metadata`, `recount_collection_documents`, `persist_document`, `content_hash_match`, `stream_upload_to_temp`, `UploadBudget`, `get_document_with_collection`.

Move from `routers/preferences.py` → `services/preferences.py`:
- `_deep_merge`, `_normalize_sensitive`, `_validate_sensitive`, `_encrypt_sensitive`, `_remove_cleared_sensitive`, `_decrypt_sensitive`, `decrypt_preferences`, `_public_preferences`.

Sweep importers:
- `services/connectors/{sync,sources,google_drive_client,google_drive_types}.py` — drop `from bigrag.routers._documents import …`.
- `services/chat/turn.py:14` — drop `from bigrag.routers.preferences import decrypt_preferences`.

After the moves, `routers/_documents.py` keeps only response shapers (`document_response`, `document_progress_response`, `parse_form_metadata`).

### 5.3 Split oversized routers (NEW splits + leftover v1 items)

| File | LoC | Proposed split |
|---|---|---|
| `routers/collections.py` | 677 | `collections.py` (CRUD) + `collections_embedding.py` (`_verify_embedding_credentials`, `_create_vector_store_collection`, `reembed_collection`, etc.) — better: push provision logic to `services/collections.py` (see §5.5). |
| `routers/admin_realtime.py` | 561 | router stays; extract generic SSE framework (`_event_frame`, `_snapshot_frame`, `_load_frame`, `_event_stream`, `_stream_response`, etc., lines 31-227) → `services/sse_stream.py`. Router shrinks to ~300 LoC of topic registrations. |
| `routers/query.py` | 523 | `query.py` (single/multi/batch) + `vectors.py` (upsert/delete) + `analytics.py` (`collection_analytics`, `list_embedding_models`). Analytics logic moves to `services/analytics.py`. |
| `routers/documents.py` | 480 | `documents.py` + `documents_global.py` (the `global_router` at `:446-481`). |
| `routers/upload_sessions.py` | 449 | `upload_sessions.py` (CRUD) + `_upload_sessions_file.py` (the 234-LoC `upload_session_file` handler with per-stage helpers). |
| `routers/documents_batch.py` | 422 | move `_persist_batch_upload_documents` + `_enqueue_batch_documents` + `_existing_documents_by_hash` + `_cleanup_stored_paths` (`:55-195`) into `services/batch_upload.py`. Router drops to ~280 LoC. |
| `routers/connectors.py` | 411 | extract OAuth handlers → `routers/connectors_oauth.py`. |
| `routers/webhooks.py` | 408 | extract delivery endpoints → `routers/webhooks_deliveries.py`. |

Also: replace side-effect router imports (`documents_batch.py:34 from bigrag.routers.documents import router`, `collection_events.py:14 from bigrag.routers.collections import router`) with explicit `APIRouter()` + `include_router(...)` in `app_factory/routers.py`.

### 5.4 Split oversized services (NEW splits)

| File | LoC | Proposed split |
|---|---|---|
| `services/webhook/dispatcher.py` | 469 | `webhook/{dispatcher,delivery,payload,http}.py` (see audit for class assignment). |
| `services/access_log.py` | 393 | `services/access_log/{middleware,flusher,payload,context}.py` (after `LogQueue` extraction). |
| `services/queue_embedding.py` | 401 | `queue_embedding/{embed,insert,__init__}.py`. |
| `services/queue_conversion.py` | 353 | `queue_conversion/{pdf_ocr,convert,__init__}.py`. |
| `services/retrieval/__init__.py` | 307 | `retrieval/{orchestrate,modes,__init__}.py` (split the 213-LoC `retrieve` function). |
| `services/event_bus.py` | 304 | `event_bus/{types,bus,__init__}.py`. |
| `services/runtime_setting_specs.py` | 674 | per-group files `runtime_setting_specs/{security,ingestion,queue,storage,backups,vector_store,search,chat,webhooks,retention}.py` + `__init__.SETTING_SPECS` aggregation. Drop `_spec(...)` helper (lines 25-49) — use `SettingSpec(...)` directly. |
| `services/runtime_settings.py` + `runtime_settings_apply.py` | 311+ | `services/runtime_settings/{registry,store,apply}.py`. |
| `services/connectors/sync.py` | 543 | `sync_runner.py` + `sync_document.py`. |
| `services/connectors/sources.py` | 377 | `sources.py` + `sync_jobs.py`. |
| `services/connectors/google_drive_client.py` | 370 | `google_drive_client.py` + `google_drive_oauth_client.py`. |
| `services/connectors/google_drive_auth.py` | 291 | `google_drive_auth.py` + `google_drive_tokens.py`. |
| `services/chat/questions.py` | 327 | `questions/{api,generation}.py`. |
| `services/chat/turn.py` | 320 | `turn/{prepare,credentials}.py`. |
| `services/storage.py` | 403 | `storage/{base,local,s3,factory}.py` + shared `_key_validation.py`. |
| `services/url_security.py` | 411 | `url_security/{validate,pin,transport}.py`. |
| `services/vector_store/__init__.py` | 386 | re-export + `facade.py` + `_util.py`. |
| `services/vector_store/qdrant.py` | 546 | keep backend; extract `_to_qdrant_filter`/`_combine_filters` → `qdrant_filter.py`. |
| `services/queue.py` + `queue_conversion.py` + `queue_embedding.py` + slimmed `queue_state.py` | — | `services/ingestion/{pipeline,convert,embed,state}.py`. |

### 5.5 Move route-handler infrastructure → services (correctness + tidy)

- `routers/collections.py:82-130 _create_vector_store_collection` + `_verify_embedding_credentials` + `_vector_store_unavailable_detail` → `services/collection_provision.py`.
- `routers/collections.py:592-677 delete_collection`/`truncate_collection` choreography → `services/collections.py::delete_collection(name)` / `truncate_collection(name)`.
- `routers/health.py:45-251` readiness + `_check_embedding_provider` + `_resolve_embedding_target` → `services/health.py`.
- `routers/query.py:454-516 collection_analytics` → `services/analytics.py`.
- `routers/documents_batch.py:55-195` orchestration → `services/batch_upload.py`.

### 5.6 `mcp_server.py` (376) → `mcp/` package

`mcp/{__init__,tools,unscoped,scoped,cli}.py`. Factor the duplicated `register_*_tools(mcp, client, pinned)` between the pinned and unpinned branches (current 95% duplication at lines 100-243 and 247-313).

---

## 6. Bug-queue triage (UPDATED vs v1 §4)

### Fixed since v1

`detail=str(exc)` sweep, embedding cache identity, allowlist HTTPS bypass, `_REFRESH_LOCKS` weakref, gdrive `response.text` leak, global-document leak for pinned keys, `Promise.allSettled` in upload session, login full-reload, logout EventSource teardown, delete-then-DB ordering, last-admin race (`with_for_update`), reembed N+1, event-token legacy fallback, chat LRU eviction, jitter math, `traceback` hoist, Python SDK SSE block parser, TS SDK retry/SSE/idempotency, Rust SDK fixes (then deleted), backup REPEATABLE READ + checksums, webhook signature timestamp + replay + parallel, crypto DNS resolve, OOXML, zip-bomb, queue atomic recovery + jitter + thread-safe init, ingestion chunk offsets + streaming conversion + single-tx persist, embedding bounded fan-out + input_type cache key + NaN guard + atomic cooldown, qdrant scroll cursor, question-suggestions parity for custom chat_base_url, idempotency single-flight + bearer csrf bypass + cors header sanitize, authz multi-value tenant filter + atomic rate-limit, caching strip-secrets + single-flight + url-encode + jitter TTL.

### STILL OPEN (priority order)

**Top 5 to ship next:**

1. **`services/vector_store/__init__.py:167, 186`** — `health_check` + `provider_health` write `f"{provider}: {exc.__class__.__name__}: {exc}"` into the admin JSON; Qdrant/Turbopuffer exceptions can embed URLs/ports/auth. Route through `_categorize_dependency_error` / `sanitize_message_text`.
2. **`middleware/auth.py:126, 138`** — cache-hit branch passes `last_used_at=None` (60-sec gate skipped → every cache hit does a Redis SETNX); cache key only set under `matched_hash or key_hash`, leaving rotation hashes cold. Two-line fix.
3. **`services/connectors/google_drive_auth.py:138` + `services/connectors/accounts.py:169`** — `account.oauth_state != state` not constant-time. Use `hmac.compare_digest`.
4. **`services/connectors/google_drive_auth.py:218-253`** — multi-process refresh race still real; `asyncio.Lock` only serialises within one event loop. Add `with_for_update()` on `session.refresh(account)` or optimistic update on `token_expires_at`.
5. **Background-path error-message leaks** — `routers/admin_realtime.py:80` (SSE error frames), `services/queue.py:_emit("failed", str(e))` at `:542` + `_update_doc(error_message=str(e))` at `:487,539`, `services/connectors/sync.py:284, 300, 415`, `routers/_documents.py:254`, `routers/documents.py:370` — sanitize all raw exception text persisted into `Document.error_message`, `ConnectorSource.last_error`, and SSE frames via `sanitize_message_text`.

**Other High still open:**

- `admin_backups.py:111` — DB committed before `enqueue_backup_job`; broker-down leaves `pending` forever.
- **Tenant scoping** (`services/connectors/accounts.py:79-89,127,181`) — see §4.6.
- **Python SDK `_core.py:112-154`** — no Idempotency-Key on retried POST/PUT/PATCH. TS SDK does this; achieve parity.
- **SDK `admin.custom(path, params)`** — assert `path.startswith("/v1/admin/realtime/")` in both SDKs.

**Medium still open:**

- `services/jobs/actors.py` — `max_retries=0` on `run_google_drive_sync`, `process_webhook_outbox`, `run_backup`, `run_cleanup`.
- `services/jobs/actors.py:36-40 enqueue_ingestion_job` — no dedupe (`SET NX bigrag:ingestion:inflight:<doc>`).
- `services/jobs/runtime.py:28-40` — double-checked init bug (thread-lock returns early on `_initialized` but never sets it).
- `services/queue.py:478-486` — cancelled events not fanout to webhooks.
- `services/queue.py:537-538` — DLQ uses both `LPUSH/LTRIM 0 999` and dramatiq DLQ. Pick one + structured `dead_letters` table.
- `services/queue.py:155-182 enqueue` — depth check ignores delayed+retry.
- `services/runtime_settings.py:262-275` — multi-worker stale-cache 5s lag; Redis pub/sub invalidation needed.
- `services/maintenance.py:37-55 acquire_backup_lock` — DELETE-then-INSERT race; switch to `INSERT … ON CONFLICT (name) DO UPDATE WHERE expires_at <= now()`.
- `services/collection_cache.py:73, 96` — `_fill_locks.pop` inside finally → cache stampede.
- `services/event_bus.py:194, 215` — discards `asyncio.ensure_future` task ref; tasks may be GC'd.
- `services/event_bus.py:114` — `self._completed` grows unbounded.
- `services/audit.py:182-212` — drops audit records silently when `_audit_queue is None`.
- `services/audit.py:96-108 _flush_batch` — swallows DB errors; lose audit batches.
- `services/webhook/dispatcher.py` — `WebhookDispatcher()` instantiated per actor call at `services/queue.py:307` and `services/jobs/actors.py:131`, defeating per-webhook semaphore.
- `services/webhook/dispatcher.py:99-124 _post_pinned` — `response.aclose()` before returning makes `response.text/json()` unsafe for any caller.
- `services/url_security.py:97-102` — IPv6 host not bracketed; `url.copy_with(host=ipv6)` emits malformed URL.
- `services/vector_store/qdrant.py:144-159, 198` — `str(e).lower()` substring heuristic; use structured client errors.
- `services/vector_store/turbopuffer.py:213-229 get_chunks` — `limit: {total: 10000}` no cursor pagination.
- `services/vector_store/__init__.py:130-143 replace_with` — closes backends inside `_swapping=True` lock; long stalls. Close outside.
- `services/embedding/registry.py:64-65` — LRU eviction `_models.popitem(last=False)` never awaits `aclose()` → httpx leaks for Voyage.
- `services/embedding/voyage.py:11` — `_API_URL` hardcoded; bypasses `pin_embedding_base_url`. Also raise typed `VoyageHTTPError(status_code=)` so 429 cooldown triggers via `is_rate_limit_error`.
- `services/embedding_rate_limit.py:118` — `time.monotonic() % 0.05` is deterministic jitter; use `random.uniform`.

**Low / hygiene** — see audits for detail; sweep alongside §5 splits.

---

## 7. App-side moves (CLEANUP_PLAN v1 §5/§6 still pending)

### Routes → features

| Route (LoC) | New location |
|---|---|
| `routes/_dashboard.api-keys.tsx` (407) | `features/api-keys/api-keys-page.tsx` |
| `routes/_dashboard.models.tsx` (218) | `features/models/models-page.tsx` |
| `routes/_dashboard.collections.$name.settings.tsx` (395) | `features/collections/settings-tab.tsx` + 4 cards (`retrieval-defaults-card`, `embedding-key-card`, `allowed-file-types-card`, `danger-zone-card`) |
| `routes/_dashboard.collections.$name.search.tsx` (249) | `features/collections/search-tab.tsx` |
| `routes/_dashboard.collections.$name.index.tsx` (187) | `features/collections/overview-tab.tsx` |
| `routes/_dashboard.collections.index.tsx` (190) | `features/collections/collections-page.tsx` |
| `routes/_dashboard.collections.$name.tsx` (101) | `features/collections/collection-layout.tsx` |
| `routes/_auth.login.tsx` (164) | `features/auth/login-page.tsx` |
| `routes/_auth.setup.tsx` (159) | `features/auth/setup-page.tsx` |
| `routes/index.tsx` (93) | `features/auth/home-redirect-page.tsx` (or replace useEffect-redirect with TanStack `beforeLoad` + `throw redirect(...)`) |

### Heavy features to split

| File (LoC) | Split |
|---|---|
| `collections/documents-tab.tsx` (820) | `documents-table.tsx` + `documents-filters.tsx` + `upload-dropzone.tsx` + `upload-session-progress.tsx` + utils (`countDuplicateNames`, `getErrorStatus`, `fileDisplayName`). |
| `overview/overview-page.tsx` (665) | `overview-access-tile.tsx` + `overview-cards.tsx` (StatusBar/StatusCount/HealthRow/QueueRow/QuickAction/Panel/MetricCard/PillLink) + constants module. |
| `mcp/mcp-page.tsx` (650) | `mcp-create-dialog.tsx` + `mcp-credential-dialog.tsx` + `mcp-detail-dialog.tsx` + `mcp-snippets.ts` + `mcp-tools.ts` + `components/ui/code-block.tsx`. |
| `chat/chat-messages.tsx` (650) | `chat-message-markdown.tsx` + `chat-assistant-message.tsx` + `chat-source-card.tsx` + `chat-latency-ledger.tsx` + `chat-user-message.tsx`. |
| `settings/tabs/instance-settings-tab.tsx` (588) | `RuntimeSettingsPanel` + `SettingControl/Row/Field/Badges` + `AdvancedSettings`. |
| `connectors/connectors-page.tsx` (442) | `google-connector-panel.tsx` + `planned-connector-panel.tsx` + `provider-header.tsx` + `provider-icon.tsx`. |
| `chat/chat-page.tsx` (394) | `use-chat-conversation.ts` hook + `chat-empty-states.tsx` (`LoadingState`, `NoCollectionsState`) + `chat-defaults.ts`. |
| `collections/create-collection-modal.tsx` (313) | split steps/sections. |
| `settings/tabs/account-tab.tsx` (307) | `ProfileForm` + `PasswordForm` + `SignOutEverywhereCard`. |
| `hooks/use-sse-snapshot-query.ts` (269) | `lib/sse-stream-pool.ts` (120 LoC pool) + `hooks/use-sse-snapshot-query.ts` (90 LoC) + `lib/use-latest-ref.ts` (4 refs). |
| `hooks/use-documents.ts` (270) | extract upload-session group → `hooks/use-upload-sessions.ts`. |

### Performance hot-spots

- `chat-page.tsx:77-86` — 11 `useChatStore` selectors → one `useShallow`.
- `google-drive-panel.tsx:59-80` — 14 selectors → `useShallow`.
- `overview-page.tsx:69-86` — `useMemo` `services`/`queueItems`.
- `chat-messages.tsx:134-213` — `useMemo([chunkCount])` on `markdownComponents`.
- `chat-messages.tsx:639-649 useAutoScrollChat` — throttle with `requestAnimationFrame` or guard on `messages.length` change only.
- `use-auth.ts:65, 75, 89, 103, 115` — narrow `invalidateQueries` to `queryKeys.auth.session()` rather than `auth.all()` (avoid re-fetching `useSetupStatus`).
- `use-auth.ts:34 useSetupStatus` — once `needs_setup === false`, set `staleTime: Infinity`.

### Other UX/native API replacements

- `document-detail-route.tsx:169` `if (!confirm(...))` → `<ConfirmDialog>`.
- `instance-settings-tab.tsx:114` `window.confirm` → `<ConfirmDialog>`.
- `account-tab.tsx:106` `window.confirm` → `<ConfirmDialog>`.
- `chat-messages.tsx:423` `window.prompt` → `<Modal>` + `<Textarea>`.
- `chat-page.tsx:330` `onResume={handleRegenerate}` — implement real resume or drop the Play button.
- `hooks/use-platform.ts:18-34 useReadiness` — switch from raw `fetch` to `apiClient` for retry/timeout parity.
- `@tanstack/react-router-devtools` — move to `devDependencies` (only used under `import.meta.env.DEV` dynamic import).

---

## 8. SDKs

### Split admin mega-files

Both Python (605 LoC) and TS (503 LoC) `admin.py`/`admin.ts` → `admin/{settings,backups,realtime,users,api_keys,access,audit,connectors,embedding_presets,mcp_servers,__init__}.py|ts`. Each sub-file ~25-180 LoC; `__init__` re-assembles `AdminResource` + shared `pagination()` helper. See audit table for exact line ranges.

### Add missing endpoints (both SDKs unless noted)

- `POST /v1/admin/api-keys/{key_id}/rotate` — **Python only** (TS already exposes `rotate`).
- `POST /v1/admin/embedding-presets/test` — **Python only** (TS exposes `test`).
- `POST /v1/admin/embedding-presets/{preset_id}/test` — **Python only** (TS exposes `testSaved`).
- `GET /v1/admin/vector-storage/overview` — both.
- `GET /v1/chat/question-suggestions` + `POST /v1/chat/question-suggestions` — both.
- `POST /v1/collections/{name}/events/token` — both.
- `GET /v1/collections/{name}/events` (SSE) — both.

### Parity fixes

- Python SDK: generate `Idempotency-Key: uuid4()` on POST/PUT/PATCH/DELETE (mirror TS `core.ts:170-174, 198-201`).
- Python `_core.py:138`: retry 5xx only when `safeToRetry` (GET/PUT/DELETE or with idempotency key) — mirror TS `core.ts:46-47, 127`.
- TS `errors.ts`: add `BadRequestError(400)`, `ConflictError(409)`, `PayloadTooLargeError(413)`, `InternalServerError(500)`, `BadGatewayError(502)`, `ServiceUnavailableError(503)`.
- Python `_errors.py:_STATUS_MAP`: add `UnprocessableEntityError(422)`, `ConflictError(409)`, `PayloadTooLargeError(413)`, `BadGatewayError(502)`, `ServiceUnavailableError(503)`.
- Both SDKs: add `next_cursor: str | null` field to all 9 list response types (`models/{auth,backup,access,webhook,collection,document}.py` parity). Without it, callers cannot paginate.
- Both SDKs: make `total: int | None` (currently typed as required) to match API which returns `null` when `include_total=false`.
- Both SDKs: narrow `provider: str` to `"openai" | "openai_compatible" | "cohere" | "voyage"` in `EmbeddingPreset`; narrow `embedding_provider` in `Collection`; narrow `default_search_mode` in `CollectionUpdate`. App currently re-narrows in `app/src/types/bigrag-api/{admin,collections}.ts` because SDKs are too loose.
- Both SDKs: pick one body-type suffix convention (`*Body` vs `*Request`).
- Both SDKs: separate `stream_timeout` from request `timeout` for SSE methods; killing long-lived streams at 120s default is wrong (TS `admin.ts:289`, Python `admin.py:300`, `chat.py:51`).
- Both SDKs: validate `admin.custom(path)` starts with `/v1/admin/realtime/`.
- Python: consolidate the **3 SSE parsers** (`_sse.py`, `resources/chat.py:_parse_frame`, `resources/admin.py:_pop_sse_frame`) into one that always returns `{event, data}`.
- Python `_sse.py` should handle `event:`, `id:`, `retry:` fields (not just `data:`).
- Python: collapse `from bigrag import types as _types; for _name in _types.__all__: globals()[_name] = ...` hack into explicit per-module re-exports (type-checker visible).
- TS: cookie handling for browser callers — `core.ts:_request` never sets `credentials: "include"`.
- TS `auth.updatePreferences(body)` posts `body` directly while server expects `{data: body}` — fix.
- TS `core.ts:7 USER_AGENT` hardcodes version; read from generated `version.ts` like Python `_version.py`.

---

## 9. Infra / configs

### docker-compose anchors

```yaml
x-bigrag-env: &bigrag-env
  BIGRAG_ENV: "${BIGRAG_ENV:-dev}"
  BIGRAG_DATABASE_URL: ...
  # ... 9 shared vars
services:
  bigrag-api: { environment: { <<: *bigrag-env, BIGRAG_HOST: 0.0.0.0, BIGRAG_UPLOAD_DIR: /data/uploads } }
  bigrag-worker: { environment: *bigrag-env }
```

Apply to both `docker-compose.yml` and `e2e/docker-compose.e2e.yml`. Saves ~30 + ~18 lines.

Also:
- `docker-compose.yml` worker `depends_on: bigrag-api { condition: service_healthy }` — drop. Worker only needs Redis/Postgres; a degraded API shouldn't block the worker.
- Worker — add a healthcheck (HTTP probe on the dramatiq prometheus port, or `redis-cli ping`).
- `app/docker-entrypoint.sh` — replace `sed __BIGRAG_CONNECT_SRC__` with `envsubst`.

### dev.sh

- Wrap the 3 wait-for-ready loops (Postgres/Redis/Qdrant) into `wait_for "<name>" "<check-cmd>" <attempts>`. 33 LoC → ~10.
- Wrap the 2 `printf '[X] %s\n'` log-prefix loops into `prefix_logs <tag>`.
- `cleanup()` — track which infra `dev.sh` actually started (`STARTED_INFRA=true` flag) and only `down` those, never a contributor's pre-existing stack.
- Centralize DSNs — source from `.env.dev` or read from docker-compose env instead of hard-coding `DATABASE_URL`/`REDIS_URL`/`QDRANT_URL`.

### CI workflows

- `.github/actions/setup-node-pnpm/action.yml` composite (Checkout + pnpm + Node + cache + install) — replace 27 duplicated lines across `sdk-typecheck`, `website-build`, `app-build`, `e2e.yml`.
- `astral-sh/setup-uv@v5` is repeated in lint + python-sdk-build + e2e + python-sdk-publish — single composite or reusable workflow.
- `ci.yml`: drop the separate `biome` job — call `pnpm biome check .` from the lint job once the composite action runs.
- `ci.yml`: drop redundant `tsc --noEmit` step in `sdk-typecheck` (the subsequent `pnpm build` runs tsc).
- `e2e.yml:34 pnpm --filter @bigrag/client build` — verify it isn't redundant with a SDK package `prepare` hook.
- Add `concurrency: group: ${{ github.workflow }}-${{ github.ref }} / cancel-in-progress: true` on `ci.yml` and `e2e.yml`.
- `docker-publish.yml:9 workflow_run` — gate on `paths:` (skip docs-only commits).
- Reduce CalVer-validation Python heredocs to `python -c "import tomllib, sys; ..."` 3-liner or move to `scripts/check-calver.py`.

### CalVer single source

`README.md:61,62, 246`, `installation.mdx:37,38, 104`, `docker.mdx:16,17,24,25,26,48,81,109`, `website/package.json:3`, `sdks/python/src/bigrag/_version.py` — 13+ lines drift between `2026.4.30` and `2026.5.7`. Introduce a release script that rewrites all of them from one source of truth.

### gitignore / dockerignore

- Add `.ruff_cache/` to root `.gitignore`; `git rm -r --cached .ruff_cache/`.
- Drop `.pytest_cache/` from `e2e/.gitignore` (covered at root).
- Drop `api/.venv/` from root `.gitignore` (covered by `.venv/`).
- `.dockerignore:2 docs/` — delete (directory doesn't exist).
- Add `**/.pytest_cache/`, `**/.ruff_cache/` to root `.dockerignore`.

### Dep hoisting

- `typescript`: `e2e=^5.7.0` → bump to `^6.0.3` (others are aligned).
- `@types/node`: `e2e=^22.10.0` → bump to `^25.8.0`.
- `pnpm@10.18.1` in `e2e/package.json:6` `packageManager` — drop (only root is honored by corepack).
- `ruff>=0.7` in `e2e/pyproject.toml` → bump to `>=0.8.0` (match api).
- Verify `pnpm.overrides.uuid@^14.0.0` is still needed.
- `pyproject.toml` `filterwarnings = ["ignore::DeprecationWarning"]` — narrow to specific known sources.

### Pre-commit / Biome

- `.pre-commit-config.yaml:27` — drop `.next-dev/` exclude.
- `biome.jsonc:46-58` — narrow `"sdks/**/*.ts"` → `"sdks/typescript/**/*.ts"`.

### Issue templates

- `.github/ISSUE_TEMPLATE/config.yml:4,7` — fix `github.com/bigint/bigrag` → `yoginth/bigrag`.
- `.github/ISSUE_TEMPLATE/bug_report.yml:38` — replace `"0.1.x or commit SHA"` placeholder with current CalVer template.

### e2e test hygiene

- 4 copies of `_wait_until_searchable` (test_query, test_chat, test_chat_suggestions, test_evaluation) → `tests/_helpers.py::wait_until_searchable`.
- `_seed_collection` pattern repeated in 5 files → `tests/_helpers.py::seed_collection`.
- TypeAlias quartet (`CollectionFactory`, `DocumentFactory`, `ApiKeyFactory`, `ApiKeyClientFactory`) redeclared in 5 files → centralize in `_helpers.py`.
- TS SDK tests: 6 copies of `beforeAll/afterAll` admin-client boilerplate → `_setup.ts::useAdminClient()`.
- Strip ~440 LoC of decorative test docstrings + section dividers across 27 test files (see audit for full file:line table).
- Split oversized tests (`conftest.py` 601, `test_query.py` 557, `test_documents.py` 552, `test_collections.py` 483, `test_webhooks.py` 499) per audit recommendations.

---

## 10. Alembic — make `0001` autogen-stable

Current `0001_initial_schema.py` **drifts from `db/models/*` on 5 check constraints**, because they're attached via `mapped_column(sa.CheckConstraint(...))` which autogenerate silently drops. Re-emit will reappear every revision.

Move these constraints into the model's `__table_args__`:
- `documents_status_check` (`db/models/document.py:48-51`) — `status IN ('pending','processing','ready','failed')`.
- `webhook_deliveries_status_check` (`db/models/webhook.py:55-58`) — `status IN ('pending','delivered','failed')`.
- `users_role_check` (`db/models/auth.py:22-23`) — `role IN ('admin','member')`.
- `collections_vector_store_provider_check` (`db/models/collection.py:38-41`) — `IN ('qdrant','turbopuffer')`.
- `embedding_presets_provider_check` (`db/models/collection.py:89-93`) — `IN ('openai','openai_compatible','cohere','voyage')`.

Then re-emit `0001_initial_schema.py` from autogenerate; verification command:
```bash
dropdb bigrag_dev && createdb bigrag_dev
cd api && uv run alembic upgrade head
uv run alembic revision --autogenerate -m drift_check
# Inspect upgrade()/downgrade() — both must be only `pass`
rm api/alembic/versions/*_drift_check.py
```

Other migration hygiene:
- `api/alembic/env.py:14` — make `_normalize_url` public (`normalize_url`) instead of importing a private symbol.
- `api/alembic/env.py:35-44 run_migrations_offline()` — drop; `alembic upgrade --sql` is not supported anywhere.
- `0001_initial_schema.py:26, 949, 1004, 1091` — strip the 4 `# ### commands auto generated by Alembic ###` comment pairs (policy parity).

Add an alembic step (or migrate models first) to:
- Drop `QueryLog.collection_id` + `idx_query_log_collection_id` (see §2).
- Drop `idx_access_log_actor`, `idx_access_log_action`, `idx_access_log_collection`, `idx_documents_collection_id` (redundant with composites).
- Make `idx_documents_collection_hash` partial `WHERE content_hash IS NOT NULL`.
- Add `idx_audit_actor_created_at`.

---

## 11. Docs sync

- README.md:74 — drop "Rust" from SDK list in Mermaid.
- README.md:327-328 — fix broken table split.
- README.md env table (~70 rows) duplicates `configuration.mdx`. Either keep README to a top-10 + link, or treat README as canonical.
- README inline endpoint-audit heredoc (lines 130-159) — move to `scripts/audit-endpoint-coverage.py`.
- README docs link line 287 — point to published docs URL, not raw `website/content/docs/sdks/mcp.mdx`.
- `website/content/docs/index.mdx:10` — drop "Rust" from SDK list.
- `website/content/docs/comparison.mdx:12` — 10-column table overflows narrow viewports; split.
- `website/content/docs/admin-ui.mdx:72` — break the 600+ char paragraph into bullet points.
- STYLEGUIDE.md (2547 lines, 78KB) — keep only project-specific guidance (~600 lines); drop the generic React/TS/Tailwind chapters or link to upstream docs.
- CONTRIBUTING.md:59 — add `sdks/python/` to project structure list.
- AGENTS.md — verify Base UI mention; update post-refactor module references if needed.
- `scripts/strip-next-env-comments.mjs` — KEEP (postbuild requirement; Next regenerates the banner on every build).
- **DELETE** `CLEANUP_PLAN.md` (this file) and `MIGRATION_PLAN.md` once the branch is merged. Remaining open items move to GitHub issues.

---

## 12. Files this plan touches (approx)

- **Delete**: ~20 (dead service modules, dead test helpers, dead npm/python deps, façades, empty `__init__.py`s, top-level docs).
- **Rename**: 6 (`_principal.py`, `Session`→`UserSession`, `services/_retrieval_filters.py`, `services/connector_registry.py`, `services/jobs/`→`services/dramatiq/`, `worker.py`).
- **Split**: ~30 (api routers + services + app features + SDK admin).
- **Merge**: ~6 (page-container/shell/header → page; google_drive.py façade into connector_registry; access_log/audit duplication into `_log_queue`; cors/csrf origin into `services/origin.py`; runtime_settings + apply; connectors/scheduler + progress into sync).
- **New shared helpers**: ~14 (`uuid_or_404`, `decode_cursor_or_400`, `ensure_embedding_or_400`, `verify_or_422`, `is_mcp_key`, `connector_callback_url`/`connector_runtime_or_404`, `is_origin_allowed`, `init_runtime`, `LogQueue`, `retry_with_backoff`, `enforce_collection_pin`, `use-auth-gate`, `use-collection-name`, `ApiUnreachable`, `Page`, `createInvalidatingMutation`, `defineFormSchema`).
- **Re-emit**: 1 (`0001_initial_schema.py` after check-constraints move).

After this branch lands the repo loses ~25 files of clutter, breaks all 4 known import cycles, plugs all known tenant-scoping gaps, brings Python SDK to parity with TS SDK, makes alembic autogen-stable, and the public surface (routes, SDK methods, public service exports) becomes more navigable.

---

## 13. Quick wins to ship first (low risk, 1-2 days)

In cost-vs-impact order:

1. **Delete the NEW dead code in §2** (~1k LoC across services, routers, db, models, config, e2e/conftest, app, sdk).
2. **Promote canonical helpers** (§4.1) — frees the file splits to be mechanical sweeps. ~80 callsites converted.
3. **Top-5 STILL OPEN security/correctness fixes** (§6 first block) — narrow-scope, contained changes.
4. **Rename `_principal.py` → `principal.py`** and **`Session` → `UserSession`** (§5.1) — 1-commit mechanical.
5. **Re-emit `0001_initial_schema.py`** with check constraints in `__table_args__` (§10) — drift-free alembic.
6. **Move `_documents` helpers into `services/documents.py`** (§5.2) — breaks 3 import cycles in one commit.
7. **`docker-compose` YAML anchors + `.gitignore`/`.dockerignore` hygiene** (§9) — small, low-risk.
8. **Strip Python SDK docstrings + add Idempotency-Key** (§3, §8) — closes the SDK parity gap.
9. **App: page-shell merge + `use-auth-gate`/`ApiUnreachable`/`use-collection-name`** (§4.3) — cuts 100+ LoC of duplication.
10. **Then** the larger structural splits (§5.3, §5.4, §5.6, §7 split table).
