# Agent 10: Audit, Access Logs, Usage, Settings

## Tested
- http://localhost:3000/audit (rendered, table loaded with 25 rows of 126)
- http://localhost:3000/access-logs (could not render; auth/render blocked, see P1 below)
- http://localhost:3000/usage (not tested in browser due to environment issues; reviewed code at /Users/yoginth/bigrag/app/src/features/usage/usage-page.tsx)
- http://localhost:3000/settings (not reached in browser; reviewed code at /Users/yoginth/bigrag/app/src/features/settings/)

NOTE ON ENVIRONMENT: Throughout the test window the browser was overwhelmed by concurrent activity from the other parallel QA agents. The dashboard layout blocks rendering on `useSession()` and `useSetupStatus()`, and those `GET /v1/auth/me` and `GET /v1/auth/setup-status` requests sat in `pending` for 30+s at a time despite the backend serving the same requests in <2ms when issued via curl. Several full reload cycles were needed just to get a single page (audit) to render once. Mid-test the dashboard kicked me to `/login`, and the login page itself then froze on its own auth check, so I could not finish exercising Access Logs / Usage / Settings end-to-end. Many findings below are therefore derived from source review and the network log, not from live click-through.

## Issues

### [P1] /v1/admin/realtime/audit returns 503 to a logged-in admin
- Route: /audit (and observed because audit-page SSE re-establishes on every navigation)
- Reproduction:
  1. Open /audit while several other tabs are also subscribed to admin SSE streams.
  2. Watch network — initial /v1/admin/realtime/audit?limit=25&offset=0 returns 200; on re-mount it returns 503 (seen twice in the same tab).
- Expected: SSE endpoint should either keep accepting the subscription or return a clean retry/backoff; never 503 for a valid admin session.
- Actual: Two recorded responses:
  - `GET http://localhost:4000/v1/admin/realtime/audit?limit=25&offset=0 -> 503`
  - `GET http://localhost:4000/v1/admin/realtime/audit?limit=25&offset=0 -> 503`
- Console: none surfaced to user.
- Network: see above.
- Suspected source: SSE broadcaster / subscriber-cap on the admin realtime endpoint in the API; unknown exact file. Likely in `api/.../admin/realtime/audit` handler — check for max-subscribers or pool exhaustion.

### [P1] Page 2 of the audit log never renders
- Route: /audit
- Reproduction:
  1. Load /audit (page 1 renders, 25 rows shown, "Page 1 of 6").
  2. Click the "Next audit page" button.
- Expected: Page 2 renders within a few seconds, showing rows 26-50.
- Actual: The audit-log card swaps to the inner spinner and stays there indefinitely (>30s in my run). Network shows `GET /v1/admin/realtime/audit?limit=25&offset=25` stuck in `pending` with no snapshot delivered, and no HTTP fallback request to `/v1/admin/audit?limit=25&offset=25` was issued.
- Console: none.
- Network: `GET http://localhost:4000/v1/admin/realtime/audit?limit=25&offset=25 -> pending` (never delivers a `snapshot` event).
- Suspected source: `app/src/hooks/use-sse-snapshot-query.ts` — the fallback in `fetchFallback()` only fires if EventSource emits `onerror` AND query data is undefined; a silently-open SSE stream that never emits `snapshot` leaves the consumer permanently in `isPending` with no recovery. Combined with the P1 above (server can 503 on this endpoint), the SSE fallback path is too narrow.

### [P2] Audit page is missing the "result" column and filters described in the spec
- Route: /audit
- Reproduction: Inspect rendered table.
- Expected (per QA spec): columns include time, actor, action, resource, result; filters for actor / action type / date range; event detail drill-down.
- Actual: Columns are WHEN | ACTOR | ACTION | RESOURCE | IP — no result/status column. There is no filter UI at all (no search, no actor picker, no action picker, no date picker). There is no row click / event-detail panel — `metadata`, `user_agent`, and the raw payload are fetched from the API (visible in `GET /v1/admin/audit`) but never surfaced to the UI. No export button either.
- Console: none.
- Network: none.
- Suspected source: `/Users/yoginth/bigrag/app/src/features/audit/audit-page.tsx` lines 86-127 (table head + body) and the surrounding `AuditPage` component — only renders 5 columns and a pager; no `<Filter />` or `<DetailDrawer />` is mounted.

### [P2] Usage page renders no chart — only stat cards and a flat per-collection table
- Route: /usage
- Reproduction: Open /usage.
- Expected (per QA spec): charts render (SVG/canvas) with tooltips; date-range picker offers "last 24h", "last 7d", "last 30d".
- Actual (from source review of `/Users/yoginth/bigrag/app/src/features/usage/usage-page.tsx`):
  - No chart is rendered at all. The page is 4 `StatCard`s + a `<table>` of per-collection rows. No `<svg>`, no `<canvas>`, no chart library import. The QA test plan's "flag if SVG/canvas is empty when there IS data" is not applicable because there is no chart component to begin with.
  - Window picker offers only `7 / 30 / 90 / 365` days — there is no "last 24h" option.
- Console: not exercised live.
- Network: not exercised live.
- Suspected source: `/Users/yoginth/bigrag/app/src/features/usage/usage-page.tsx` (entire file — page composition lacks chart and 24h option).

### [P2] Sustained dashboard render stalls under modest concurrent load (HTTP/1.1 connection starvation)
- Route: all dashboard pages (/audit, /access-logs, /usage, /settings, /login)
- Reproduction:
  1. With multiple browser tabs (other QA agents in parallel) subscribed to dashboard pages that hold open EventSource streams, navigate to any new dashboard page.
  2. The new tab's `GET /v1/auth/me` and `GET /v1/auth/setup-status` sit in `pending` for tens of seconds.
- Expected: Auth check should not block on unrelated SSE traffic; the page should render quickly even when other tabs hold open streams.
- Actual: The dashboard layout `(app/src/layouts/dashboard-layout.tsx` lines 29-35) shows a full-page Spinner while `isPending || !session`. With the local API on HTTP/1.1, each open SSE stream (`/v1/admin/realtime/audit`, `/v1/collections/{name}` realtime, `/v1/admin/realtime/usage`, etc.) consumes one of the browser's ~6 connections-per-origin. With 4-5 SSE streams already open across tabs, even fast endpoints like `/v1/auth/me` queue behind them and stall, which freezes the whole dashboard behind the Spinner gate.
- Console: only Vite connect/connected logs.
- Network: e.g. `GET http://localhost:4000/v1/collections/arxiv -> pending` x3, `GET /v1/admin/realtime/audit -> pending`, plus `auth/setup-status` and `auth/me` queued behind them, all unresolved.
- Suspected source: combination of:
  - Backend served over HTTP/1.1 with no HTTP/2 multiplexing — see vite/api server config.
  - `app/src/layouts/dashboard-layout.tsx` (lines 29-35) using a full-screen blocking spinner with no auth-cache priming.
  - `app/src/hooks/use-sse-snapshot-query.ts` opens a new EventSource on every mount (even when a sibling tab already has one for the same key).
- Mitigation suggestion: serve the API over HTTP/2 in dev, or prime `useSession` from a cached value while the request is in flight so the dashboard frame can render and the rest can stream in.

### [P3] /v1/admin/audit response leaks raw `metadata` to admin UI consumers — verify no secrets get logged into metadata
- Route: /audit (data layer, not UI)
- Reproduction:
  1. `fetch('http://localhost:4000/v1/admin/audit?limit=25&offset=0', {credentials:'include'})` as admin.
  2. Inspect `entries[i].metadata` and `entries[i].user_agent`.
- Expected: `metadata` is documented as a safe map; no plaintext secrets, no API key values, no passwords (only hashed/redacted references).
- Actual: For my test data the only metadata I could inspect was `{email: "yoginth@hey.com"}` on an `auth.login_failed` row — that is fine. But because there is no UI filter for `action`, I could not sample, e.g., `api_key.create` rows to confirm the API-key plaintext value isn't recorded in metadata. The Claude-in-Chrome shim did flag/redact something in the response (`api_key_id: "[BLOCKED: Sensitive key]"`) which means the shim's heuristics are matching the API-key-id field — that's the shim being conservative, not necessarily a backend bug. Worth a one-time audit of the audit table's metadata for any action type that touches secret material (api_key.create, api_key.rotate, auth.password_change, master_key.*).
- Console: none.
- Network: `/v1/admin/audit` 200.
- Suspected source: backend audit recorder — wherever `audit::record` is called for api-key / auth / master-key actions. Verify with `grep audit.*record` on the API source.

### [P3] No visible per-status filter / sort on /access-logs (source-review finding only)
- Route: /access-logs
- Reproduction: review `/Users/yoginth/bigrag/app/src/routes/_dashboard.access-logs.tsx`.
- Expected (per QA spec): filter by status code (4xx/5xx), path, date; sort by latency.
- Actual: The component renders a fixed list with stat cards (Events, Success rate, P95 latency, Query events) and a flat stream of 100 most-recent entries from `useAccessLogs({ limit: 100 })`. No filter inputs, no sort controls; only a Refresh button. So the "flag slowest call >2000ms" test is not directly supported in the UI — the overview "P95 latency" stat is the only latency surface and the per-row latency is shown but not sortable.
- Console: not exercised live.
- Network: not exercised live.
- Suspected source: `/Users/yoginth/bigrag/app/src/routes/_dashboard.access-logs.tsx` lines 18-95 (component) and `/Users/yoginth/bigrag/app/src/hooks/use-access-logs.ts` (only supports a `limit` arg, no status/path/date params).

### [P3] /access-logs renders nothing meaningful to non-admins instead of redirecting
- Route: /access-logs
- Reproduction: source review.
- Expected: non-admins are either redirected, or shown a friendly empty state.
- Actual: The component returns a "Admin access required" panel — that's fine — BUT the gate fires on `session?.user.role === "admin"`, and while `session` is undefined (loading), `canSeeAccess` is `false`, so `useAccessOverview(false, 7)` and `useAccessLogs({limit:100}, false)` are called with `enabled=false` and the page momentarily shows the gate-allowed shell. Minor UX nit; not a P1.
- Console: none.
- Network: none.
- Suspected source: `/Users/yoginth/bigrag/app/src/routes/_dashboard.access-logs.tsx` lines 19-40.

## Notes
- Slowest /v1 call observed: I could not measure /v1 latencies under normal browser flow because of P2 (connection starvation). Direct-curl on the backend stayed at 1-5ms throughout (`/v1/auth/me 401 1.5ms`, `/v1/auth/setup-status 200 5ms`). The actual user-perceived latency on /audit's first paint exceeded **45 seconds** end-to-end in my session.
- Audit table top row in my session: `auth.login_failed` at 127.0.0.1, actor `yoginth@hey.com`, user_agent `curl/8.7.1`, with `metadata: {email: "yoginth@hey.com"}`. This was caused by my own curl probe earlier in the run; not a real bug, but worth noting that failed-login attempts are recorded with the attempted email in metadata (acceptable, just a heads-up).
- Sidebar groups Access Logs, Usage, Audit under "OBSERVABILITY" and Backups, Vector Storage, Settings under "ADMINISTRATION" — consistent with the spec routes.
- The Settings tab nav (per `/Users/yoginth/bigrag/app/src/features/settings/settings-navigation.ts`) is Account / Health / Security / Data — there is no top-level "Theme" toggle in Settings (a Theme switcher does live in the user/login screens though, per the login page content "Skip to content / Theme / bigRAG").
- The spec referenced overview metrics of "46 events / P95 4423ms" — these should map to the `Stat` cards on /access-logs. I could not visually confirm because the page never rendered in browser; the source confirms the same overview fields are shown (`total_events`, `p95_latency_ms`).
- Several requests to localhost:4000 are currently being silently masked by the Claude-in-Chrome shim's classnames (`[BLOCKED: JWT token]`, `[BLOCKED: Sensitive key]`, `[BLOCKED: Cookie/query string data]`). This is the shim, not the app — but worth flagging that admins reviewing audit data through this shim will see redacted UUIDs even when the underlying value is safe (e.g., api_key_id is not actually sensitive).
