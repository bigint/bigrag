# Agent 7: API Keys & MCP

## Tested
- /api-keys (page repeatedly stuck in indefinite loading spinner; data never rendered during this run)
- /mcp (eventually rendered "No MCP servers yet" empty state after ~70s wait)

Source files inspected:
- /Users/yoginth/bigrag/app/src/routes/_dashboard.api-keys.tsx
- /Users/yoginth/bigrag/api/bigrag/routers/admin_api_keys.py
- /Users/yoginth/bigrag/api/bigrag/middleware/auth.py

## Issues

### [P1] Admin endpoints (/v1/admin/api-keys, /v1/admin/mcp-keys) hang or return 503 under modest concurrent load
- Route: /api-keys and /mcp
- Reproduction:
  1. Open /api-keys (or /mcp) while other authenticated tabs are also issuing requests.
  2. Observe the page sits on the loading spinner indefinitely.
  3. Inspect network — `GET http://localhost:4000/v1/admin/api-keys` stays `pending` for 50-90+ seconds, then begins returning HTTP 503.
- Expected: Endpoint returns a JSON list within a second or two; never 503 under <10 concurrent authenticated callers.
- Actual: Repeated `pending` requests followed by `503` for both `/v1/admin/api-keys` and `/v1/admin/mcp-keys` (and intermittently `/v1/auth/me`, `/v1/auth/setup-status`, `/v1/collections?limit=200`). When unauthenticated, the same endpoints return `401` in ~2ms — so the slowdown is in the authenticated path.
- Console: no JS errors
- Network: many `pending` then `503` Service Unavailable responses on `/v1/admin/api-keys`, `/v1/admin/mcp-keys`, `/v1/auth/me`, `/v1/auth/setup-status`. Unauth direct curl to `/v1/admin/api-keys` returns 401 in ~1.7ms.
- Suspected source: DB session/connection pool exhaustion or a long-held lock in the authenticated request path. Look at `get_session` / Redis cache pattern in `api/bigrag/middleware/auth.py:163-219` and `api/bigrag/routers/admin_api_keys.py:65-78`. The list query also issues a second `count(*)` against a JSON path predicate (`ApiKey.permissions["mcp"].is_(None)`) which may not be indexed and could compound under load.

### [P2] /api-keys gives no error UI when its data request fails (503)
- Route: /api-keys
- Reproduction:
  1. While the backend returns 503 on `/v1/admin/api-keys`, load /api-keys.
  2. The page renders only the loading spinner.
- Expected: An error banner like "Couldn't load keys — retry", or at least an indication that the request failed.
- Actual: Infinite loading spinner; user has no signal that anything went wrong.
- Console: none
- Network: `/v1/admin/api-keys` returns 503
- Suspected source: `app/src/routes/_dashboard.api-keys.tsx` uses `useApiKeys()` and only checks `isPending` to show the loading state — `isError`/`error` from React Query is ignored. Add an error branch to the `DataTable` / page surface.

### [P2] /mcp gives no error UI when its data request fails (503)
- Route: /mcp
- Reproduction:
  1. While the backend returns 503 on `/v1/admin/mcp-keys`, load /mcp.
  2. The page sits on "Loading MCP servers..." indefinitely.
- Expected: Visible error state.
- Actual: Loading spinner persists; no indication of failure.
- Console: none
- Network: `/v1/admin/mcp-keys` returns 503
- Suspected source: equivalent `useMcpKeys`-style hook + page component for MCP; same fix needed.

### [P2] Create API key modal lacks scope picker (read/write/admin) and expiration picker
- Route: /api-keys (New key modal)
- Reproduction:
  1. Click "New key" on /api-keys.
  2. Inspect the form fields.
- Expected (per QA spec): name, scope picker (collections multi-select + permission scopes read/write/admin), expiration picker.
- Actual: Only `Name` (text input) and `Collection scope` (single-select dropdown of "All collections" + each collection). No permission scope picker, no expiration picker, no multi-select for collections.
- Suspected source: `app/src/routes/_dashboard.api-keys.tsx:172-229` — the modal only renders `name` and a single `collection` field. The backend (`api/bigrag/routers/admin_api_keys.py:81-127`) accepts `scopes` and `expires_at` but the UI never sets them.

### [P2] No "rotate" flow on API keys page
- Route: /api-keys
- Expected: Rotate flow with confirmation guard.
- Actual: Row actions only expose a toggle (active/revoked) and a Delete (revoke) button. No way to rotate without revoking and re-creating.
- Suspected source: same file as above — no rotate handler in `useApiKeys` hooks or the row action column.

### [P3] No "test connection" button for MCP servers
- Route: /mcp
- Expected: Some way to validate the rendered snippet works against the backend.
- Actual: Empty state only offers "Create your first MCP" — no diagnostic action surface even after a server is created (only inferred from source; no MCP server existed during the run to exercise).

### [P3] Page sessions can race / be hijacked
- Route: any
- Observation: Multiple tabs of the same dashboard navigating between routes in parallel caused other tabs to be logged out (redirected to `/login`) while the affected backend was returning 503s on `/v1/auth/me`. While this was triggered by 10 parallel QA agents, in production this could mean a single 503 on `/v1/auth/me` kicks an active user back to login instead of retrying.
- Suspected source: auth context probably treats any non-2xx from `/v1/auth/me` as "not authenticated" instead of distinguishing 401/403 from 5xx.

## Notes
- Cleanup status: **No qa-* key was created or revoked** because the underlying `/v1/admin/api-keys` `GET` never returned during this run, so the page never rendered far enough to open the create modal. Nothing to clean up.
- Direct backend probe: `curl http://localhost:4000/v1/admin/api-keys` (no cookie) → `401` in ~1.7ms consistently. Same endpoint via authenticated browser session → 50-90s `pending` then `503`. The authenticated path is the regression.
- The list-keys endpoint at `api/bigrag/routers/admin_api_keys.py:71-77` runs two queries (a `SELECT … ORDER BY created_at DESC LIMIT … OFFSET …` and a `SELECT count(*)`) both with a `ApiKey.permissions["mcp"].is_(None)` JSON-path predicate; worth verifying there's an index that covers this or precomputing the `count` differently.
- The MCP page's empty state has no per-client (Claude Desktop / Cursor / generic) install snippets — those presumably only render after at least one MCP server is created. Could not exercise that flow given the 503 state.
