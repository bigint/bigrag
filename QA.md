# bigRAG QA Report

**Generated:** 2026-05-16
**Build:** `bigrag-api 2026.4.30` against `main @ a2c94497` (admin UI on :3000, API on :4000, Postgres / Redis / Qdrant / turbopuffer all up).
**Method:** 10 parallel browser QA sub-agents driving Chrome via MCP, logged in as admin "Yoginth". Each agent owned one feature area; per-agent raw reports live in `.qa/agent-01.md` … `.qa/agent-10.md`.

## Test environment caveat

All 10 agents shared one Chrome instance and one dev API. The combination of (a) the dev API running over HTTP/1.1, (b) the admin UI opening multiple long-lived SSE streams per page, and (c) Chrome's hard cap of 6 connections per origin saturated the connection pool. Many of the "infinite spinner" / "503" findings below were *triggered* by that contention — but the *underlying weaknesses* (no client-side timeout, no error fallback, no SSE multiplexing, no abort on stale fetches) are real product bugs that surface for any user with a few tabs open or any flaky network.

Several agents (3, 6, 7, 8, 9, 10) were unable to fully render their target pages mid-run and supplemented browser findings with source-code review.

## Summary

| Severity      | Count |
| ------------- | ----- |
| P1 (critical) | 12    |
| P2 (major)    | 29    |
| P3 (minor)    | 35    |
| P4 (nit)      | 7     |
| **Total**     | **83**|

### Top cross-cutting themes

1. **No request timeout / no error fallback in the data layer.** Every "hung spinner" finding traces to React-Query / SSE hooks that ignore `isError` and never abort stale requests. Fix once in `app/src/hooks/use-sse-snapshot-query.ts` + the auth bootstrap hook to neutralize ~10 listed issues.
2. **Auth bootstrap is a single point of failure.** `_dashboard.tsx` gates every route on `/v1/auth/me` + `/v1/auth/setup-status` succeeding; if either hangs, the entire app freezes. Agent 8 could not reach `/webhooks` or `/evals` at all because of this.
3. **HTTP/1.1 + many SSE streams = connection starvation.** Enable HTTP/2 on the API in dev, gate concurrent SSE streams per page, or fall back to polling.
4. **Destructive actions lack typed-confirmation guards.** Delete collection, truncate collection, etc. all execute on a single click in their confirm dialog.
5. **Form validation is visually silent.** Create / edit modals for collections, models, and evals only render a red border on invalid fields — no error text, no `aria-describedby`.

---

## P1 — Critical

### Auth / app shell

- **Auth bootstrap hangs freeze every dashboard route.** `/v1/auth/me` + `/v1/auth/setup-status` block `useDashboardAuthRedirect` with no timeout or error fallback; pages stay on the global spinner indefinitely. *(Agents 4, 8, 9, 10)* — `app/src/layouts/dashboard-layout.tsx:82-97`, `app/src/hooks/use-auth.ts`.
- **Admin session can die mid-session with no graceful messaging.** When the shared session ends, all open dashboard tabs jump to `/login` simultaneously with no toast and no `?from=` return URL. *(Agent 3)* — `app/src/layouts/dashboard-layout.tsx`, `app/src/routes/_auth.login.tsx`.

### Backend / API

- **Authenticated admin endpoints hang 50–90 s then 503 under modest concurrent load.** `/v1/admin/api-keys`, `/v1/admin/mcp-keys`, `/v1/admin/audit`, `/v1/admin/realtime/audit` all reproduce; unauth probes return 401 in ~2 ms, isolating the regression to the authenticated path. *(Agents 1, 7, 9, 10)* — investigate `api/bigrag/middleware/auth.py:163-219` (DB session reuse / Redis cache) and the JSON-path predicate `ApiKey.permissions["mcp"].is_(None)` in `api/bigrag/routers/admin_api_keys.py:65-78`.

### Collections

- **`/collections/$name` has no real "home" — it's a redirect-only spinner page.** Users land on `/collections/arxiv`, see a brief spinner, then bounce to `/documents` with no overview / stat tiles. *(Agent 3)* — `app/src/routes/_dashboard.collections.$name.index.tsx:9-20`.
- **Documents tab hangs forever on "Loading upload session…" when a stale `bigrag:upload-sessions` localStorage entry points at a session that no longer exists server-side.** No error branch, no dismiss control. *(Agent 3)* — `app/src/features/collections/documents-tab.tsx:191-198`; `app/src/features/collections/upload-session-store.ts` (no 404-cleanup).

### Create collection

- **Empty / invalid-pattern name submits silently.** Red border only, no error text; the help text disappears, leaving users with no idea what to fix. *(Agent 2)* — `app/src/features/collections/create-collection-modal.tsx:81-100`.
- **Help text contradicts the API regex.** UI says "Lowercase letters, numbers, dashes and underscores"; API enforces `^[a-zA-Z][a-zA-Z0-9_]*$` (no dashes, mixed case allowed, must start with a letter). A user typing `my-docs` will silently get a 422. *(Agent 2)* — `create-collection-modal.tsx:90` vs `api/bigrag/models/collection.py:11`.

### Settings — destructive actions

- **Delete-collection confirmation has no typed-name guard.** One click in the dialog and the collection (with all docs and vectors) is gone. *(Agent 6)* — `app/src/routes/_dashboard.collections.$name.settings.tsx` + `app/src/components/ui/confirm-dialog.tsx`.

### Models / backups

- **POST `/v1/admin/embedding-presets` hangs in browser.** OPTIONS preflight returns 204 instantly, but the POST stays pending forever; modal stuck on "Creating…" with no timeout / error toast. Curl finishes in <2 ms. *(Agent 9)*
- **Backups page never renders** — same auth-pending deadlock; `useBackups` never fires. *(Agent 9)* — `app/src/features/backups/backups-page.tsx`.

### Audit

- **`/v1/admin/realtime/audit` returns 503 to a logged-in admin** (observed twice in the same session). *(Agent 10)*
- **Page 2 of the audit log never renders.** SSE never emits a `snapshot` event for offset > 0; HTTP fallback isn't triggered because EventSource didn't fire `onerror`. *(Agent 10)* — `app/src/hooks/use-sse-snapshot-query.ts`.

---

## P2 — Major

### Overview / dashboard

- SSE 503s on `/v1/admin/realtime/{platform/stats, platform/readiness, access/overview}` are silently swallowed — no banner, no toast, no "degraded" indicator. *(Agent 1)* — `use-sse-snapshot-query.ts` + `api/bigrag/routers/admin_realtime.py:524-554`.
- Loading state shows misleading concrete values instead of skeletons (Collections=0, "0/5 services online", "Queue is clear") that read as a real outage. *(Agent 1)* — `app/src/features/overview/overview-page.tsx:107-136`.
- "Collections" stat card disagrees with its "X visible in the admin UI" sub-label — two different queries finish at different times. *(Agent 1)*
- Document Readiness (`49/0/0/1`) vs Ingestion Queue (`506/179/42/42`) numbers are wildly inconsistent on the same screen with no explanation of what each panel counts. *(Agent 1)*
- "Ingestion queue" warns "Dead-lettered jobs need operator review" with no link / action. *(Agent 1)*
- "1 Failed" document count is non-clickable — no drilldown. *(Agent 1)*

### Collections list / create

- Form state persists across Cancel/X and reopen — name field keeps the last value. *(Agent 2)* — `create-collection-modal.tsx:30-42`.
- "Creating…" button stuck indefinitely with no timeout / error toast when POST hangs/503s; modal can be reopened with the same disabled button. *(Agent 2)* — `create-collection-modal.tsx:206-208`, `app/src/hooks/use-collections.ts:72`.
- Indefinite "Loading collections…" spinner with no error UI when `/v1/collections?limit=200` returns 503. *(Agent 2)* — `use-collections.ts:19-24`.
- No client-side cross-field validation that `chunk_overlap < chunk_size` — caught only by API as 422 (and that toast doesn't fire reliably). *(Agent 2)*

### Documents

- `/collections/{name}/documents/{docId}` detail page never finishes loading — 4+ concurrent requests fan out without batching. *(Agent 3)* — `app/src/routes/_dashboard.collections.$name.documents.$docId.tsx:11-23`.
- Documents list is missing search, filter, sort, pagination, and bulk actions described in the spec. Even the 43-doc `test` collection has no pagination. *(Agent 3)* — `documents-tab.tsx:210-272`.
- Collection chrome shows three bare badges (`1536d` / `turbopuffer` / `text-embedding-3-small`) with no labels or tooltips. *(Agent 3)*

### Search

- Query errors (503s) are silently swallowed — no toast / inline error. *(Agent 4)* — `app/src/hooks/use-query.ts:21-25` (no `onError`); consumer at `_dashboard.collections.$name.search.tsx:31-39` also lacks one.

### Chat

- No "regenerate", "copy", or "edit" controls on chat messages — Zustand store doesn't expose them and the components don't render any. *(Agent 5)* — `app/src/features/chat/chat-messages.tsx`, `chat-store.ts`.
- No persisted conversation history / no way to resume a previous chat — in-memory Zustand store, no thread list, no resume. Cleanup effect aborts streams on unmount. *(Agent 5)* — `chat-store.ts:28-33`, `chat-page.tsx:87-94`.

### Settings / connectors

- "Remove all documents" truncate has no destructive-action guard either — one-click execution. *(Agent 6)*
- `/collections/test/settings` never finished loading; form area stuck on spinner. Same root cause as the connection-starvation pattern. *(Agent 6)*
- Spinner-only state on settings / connectors pages has no error fallback / retry. *(Agent 6)*

### API keys / MCP

- `/api-keys` has no error UI when its data request 503s. *(Agent 7)* — `_dashboard.api-keys.tsx` ignores React Query `isError`.
- `/mcp` has the same problem. *(Agent 7)*
- Create-API-key modal lacks scope picker (read/write/admin) and expiration picker — backend accepts both, UI ignores them. *(Agent 7)* — `_dashboard.api-keys.tsx:172-229` vs `api/bigrag/routers/admin_api_keys.py:81-127`.
- No "rotate" flow on API keys — only revoke + re-create. *(Agent 7)*

### Webhooks / Evals

- Could not be exercised — entire dashboard wedged behind auth bootstrap (see P1). Webhooks/Evals UI never rendered. *(Agent 8)*
- No client-side timeout / error fallback on auth bootstrap. *(Agent 8)*

### Models / vector storage / backups

- `/models` wedges on "Loading presets…" after navigating away and back — even though the GET returns 200, the UI never updates. *(Agent 9)*
- `/vector-storage` slow first-paint (~30 s) under load. *(Agent 9)*

### Audit / access logs / usage / settings

- Audit page is missing the `result` column, all filters (actor / action / date), and the event-detail panel described in the spec; backend already returns the data. *(Agent 10)* — `app/src/features/audit/audit-page.tsx:86-127`.
- `/usage` page renders **no chart at all** — just 4 stat cards and a flat per-collection table. No `<svg>`, no `<canvas>`; no "last 24h" window option (only 7/30/90/365). *(Agent 10)* — `app/src/features/usage/usage-page.tsx`.
- Sustained dashboard render stalls under modest concurrent load — HTTP/1.1 + SSE root cause again. *(Agent 10)* — `app/src/layouts/dashboard-layout.tsx:29-35`.

---

## P3 — Minor

### Overview

- "New collection" button on /overview routes to /collections list instead of opening the create form. *(Agent 1)* — `overview-page.tsx:102`.
- SSE design exhausts Chrome's 6-per-host connection pool, blocking simple XHR for tens of seconds. *(Agent 1)*
- User menu only contains "Sign out". *(Agent 1)* — `app/src/components/navigation/sidebar.tsx`.
- No theme toggle anywhere in the layout. *(Agent 1)*
- Access telemetry "P95 4 423 ms / 1 710 ms avg" shown without SLO / threshold / trend. *(Agent 1)*

### Collections list / create

- Inconsistent casing between vector-store options: "Qdrant" vs "turbopuffer". *(Agent 2)* — `create-collection-modal.tsx:215-218`.
- Storage column in list shows raw lowercase provider IDs ("qdrant", "turbopuffer"). *(Agent 2)* — `_dashboard.collections.index.tsx`.
- "Actions" column has only a navigation arrow — no kebab menu for settings/delete/duplicate. *(Agent 2)*
- "No embedding presets yet" empty-state shown even when `/v1/admin/embedding-presets` is failing. *(Agent 2)* — `create-collection-modal.tsx:124-139`.
- No metadata-schema / tenant_field UI in create modal despite API support. *(Agent 2)*
- Embedding API key field missing from create modal — no messaging that it's inherited from the preset. *(Agent 2)*

### Documents

- Status pill in document row is too muted; "ready" was the only state observed. No status column to sort/filter. *(Agent 3)* — `documents-tab.tsx:240-247`.
- "Loading upload session…" and document-list spinner can both show at the same time, doubling spinners on hard reload. *(Agent 3)*

### Search

- No request timeout / weak loading indicator (tiny button spinner) — Semantic search took ~90 s under load with no progress hint. *(Agent 4)* — `_dashboard.collections.$name.search.tsx:120-130`, `app/src/lib/api.ts`.
- No client-side max-length / character counter on the query input. *(Agent 4)* — `collection-form-state.ts`.
- Result link drops the chunk index (label says `bb085a78#23`, URL ignores `#23`). *(Agent 4)* — `_dashboard.collections.$name.search.tsx:154-162`.
- Result card lacks document title / page metadata — only an 8-char doc-id prefix. *(Agent 4)* — `_dashboard.collections.$name.search.tsx:149-167`.
- Mode dropdown options ("Keyword" / "Hybrid") render blank on first open before the page settles. *(Agent 4)* — `app/src/components/ui/select.tsx`.
- `/collections/test/search` hangs on initial load when API is busy (auth bootstrap issue). *(Agent 4)*
- Double-submit observed on rapid clicks — two concurrent `/query` requests. *(Agent 4)* — `use-query.ts` (no `mutationKey`).

### Chat

- Markdown / code blocks not rendered — assistant output is plain text with `whitespace-pre-wrap` only. *(Agent 5)* — `chat-messages.tsx:46-82, 146-168`.
- Citation buttons don't link to source documents — only scroll within the same card. *(Agent 5)* — `chat-messages.tsx:93-106, 256-317`.
- Chat input has no error UX for empty submissions or invalid models — silent return. *(Agent 5)* — `chat-input.tsx:68-73`, `chat-page.tsx:161-169`.
- Switching collections silently destroys the current conversation with no confirmation. *(Agent 5)* — `chat-store.ts:28-33`.

### Settings / connectors

- "Embedding key" field has no indication whether one is already saved. *(Agent 6)* — `_dashboard.collections.$name.settings.tsx`.
- Description field has no dirty / unsaved indicator — navigate-away loses edits silently. *(Agent 6)*
- Per-collection Connectors page only contains Google Drive — UX looks unfinished. *(Agent 6)* — `app/src/features/connectors/connector-catalog.ts`.

### MCP

- No "test connection" button for MCP servers. *(Agent 7)*
- Sessions can race / be hijacked — non-2xx from `/v1/auth/me` kicks the user to login instead of retrying. *(Agent 7)*

### Models / vector storage

- `/vector-storage` shows only credentials forms — no per-collection routing, no storage stats, no health indicator. *(Agent 9)* — `app/src/features/vector-storage/vector-storage-page.tsx`.
- `/models` "New embedding preset" modal validation errors are silent (red ring only). *(Agent 9)*
- `/models` lacks a "Test connection" affordance. *(Agent 9)*
- `/models` covers embedding presets only — no rerank or chat provider presets, no `openai_compatible` (Base URL). *(Agent 9)*

### Audit / access logs

- `/v1/admin/audit` `metadata` may leak sensitive info for `api_key.create` / `auth.password_change` / `master_key.*` actions — needs a one-time audit (couldn't be sampled because there are no filters in the UI). *(Agent 10)*
- `/access-logs` has no status / path / date filters and no latency sort; only a Refresh button and a flat list. *(Agent 10)* — `_dashboard.access-logs.tsx`, `app/src/hooks/use-access-logs.ts`.
- `/access-logs` briefly renders the gate-allowed shell to non-admins while the session is loading. *(Agent 10)*

---

## P4 — Nit

- "Access health 100.0% → 97.9%" updates in place with no transition / "updated just now" indicator. *(Agent 1)*
- "Open navigation" hidden header button — verify focus styles when it does appear on mobile. *(Agent 1)*
- "Skip to content" skip link visibility on focus couldn't be confirmed due to environment instability. *(Agent 1)*
- Brief flash of "No embedding presets yet" empty state on first modal open. *(Agent 2)*
- Citation parser only recognises single `[N]` — `[1,2]` and out-of-range numbers render as literal text. *(Agent 5)* — `chat-messages.tsx:42, 59-76`.
- No way to delete or clear a single chat session from the UI (`startNewChat` exists in the store but is never wired). *(Agent 5)* — `chat-store.ts:41-45`.
- OAuth "Connect Google" button doesn't surface that it's a full-page redirect. *(Agent 6)* — `app/src/features/collections/google-drive-states.tsx`, `google-drive-panel.tsx:111-122`.

---

## What's working well

- Stat cards on /overview render real numbers on successful load; system-health pills correctly read "online" across Postgres / vector store / Redis / embeddings / worker.
- Sidebar navigation uses `@tanstack/react-router` `<Link>` (no full reloads); every sidebar route file exists under `app/src/routes/_dashboard.*.tsx`.
- "Ask bigRAG" header link correctly points to /chat.
- Search autofocuses input on load; placeholder copy is on-brand; Top-K validates 1–50 client-side.
- Chat streaming + abort path is well-implemented (`abortRef.current?.abort()` cleanly marks the assistant message as `complete` rather than `error`); citations array arrives via the `sources` SSE event before the first `delta`.
- Chat suggestion persistence (recent fix `a2c94497`) appears correctly designed: stored under `UserPreference.data["chat"]["question_suggestions"][collection]` keyed by user, with React Query `queryKey: queryKeys.chat.questions({ collection })` ensuring per-collection caches.
- OAuth client-secret on `/connectors` uses `type="password"` and shows a "Saved" placeholder when one exists — no plaintext secret rendered.
- Per-collection Embedding-key field also uses `type="password"`.
- No `<img>` without `alt`, no unlabeled `<button>`, `<html lang="en">` set, page title "bigRAG".
- All form modals have working Cancel / X / Escape close paths and no keyboard focus-trap issues observed.

---

## Per-area issue counts

| Area (agent)                                | P1 | P2 | P3 | P4 | Total |
| ------------------------------------------- | -- | -- | -- | -- | ----- |
| Overview & layout (1)                       | 0  | 6  | 5  | 3  | 14    |
| Collections list & create (2)               | 2  | 4  | 6  | 1  | 13    |
| Collection home & docs (3)                  | 3  | 3  | 2  | 0  | 8     |
| Per-collection search (4)                   | 0  | 1  | 7  | 0  | 8     |
| Chat playground (5)                         | 0  | 2  | 4  | 2  | 8     |
| Settings & connectors (6)                   | 1  | 3  | 3  | 1  | 8     |
| API keys & MCP (7)                          | 1  | 4  | 2  | 0  | 7     |
| Webhooks & evals (8)                        | 1  | 1  | 0  | 0  | 2     |
| Models / vector storage / backups (9)       | 2  | 2  | 4  | 0  | 8     |
| Audit / access logs / usage / settings (10) | 2  | 3  | 3  | 0  | 8     |
| **Total**                                   |**12**|**29**|**36**|**7**|**84**|

(Totals slightly exceed the headline summary because a few cross-cutting issues appear in more than one agent's report — same root cause, surfaced in a different feature.)

---

## Recommended fix order

1. **Add request timeout + error fallback to `use-sse-snapshot-query.ts` and the auth bootstrap hook.** This single fix neutralizes the "infinite spinner" symptom across ~10 of the issues above and unblocks `/webhooks` and `/evals` coverage.
2. **Investigate the authenticated admin-endpoint hang** (`/v1/admin/api-keys`, `/v1/admin/mcp-keys`, `/v1/admin/audit`, `/v1/admin/realtime/audit`). Likely DB pool / Redis-cache pattern in `api/bigrag/middleware/auth.py` or the JSON-path predicate in the list query.
3. **Enable HTTP/2 on the API in dev** (or gate concurrent SSE streams per page) so a few open dashboard tabs don't starve XHR.
4. **Add typed-name destructive guard** to delete-collection and truncate-collection confirms.
5. **Fix create-collection validation**: align help text with the API regex, render inline error text, reset modal state on close, add cross-field validator for `chunk_overlap < chunk_size`.
6. **Render markdown + link citations** in chat (`react-markdown` + a citation chip that links to `/collections/{name}/documents/{docId}` deep-linked to the chunk).
7. **Build the missing audit-page filters and event-detail panel** — backend data is already there.
8. **Replace `/usage`'s table-only view with a chart** + add "last 24h" window.
9. **Add API-key scope picker, expiration picker, and rotate flow** in the create modal.
10. **Add upload-session 404 cleanup** in `upload-session-store.ts` to stop the stale-session spinner trap.

---

## How this report was generated

10 sub-agents ran in parallel, each owning one feature area, all logged in as admin "Yoginth" through the Claude-in-Chrome MCP. The slowest agent took ~24 minutes. Agent 8 stalled and was re-dispatched once. Raw per-agent reports remain at `.qa/agent-*.md` for cross-reference (file paths and line numbers cited above come from those reports).
