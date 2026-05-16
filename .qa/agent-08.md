# Agent 8: Webhooks & Evals

## Tested
- http://localhost:3000/webhooks — never rendered past the global app-bootstrap loading spinner.
- http://localhost:3000/ — same loading-spinner state, same blocking requests.
- Re-navigated multiple times over ~90s; same result.
- /evals — NOT reached. The frontend never gets past auth bootstrap, so no /evals work was possible.

## Issues
### [P1] Entire dashboard wedged behind hung `/v1/auth/setup-status` and `/v1/auth/me` requests
- Route: all `_dashboard.*` routes including /webhooks and /evals (also /)
- Reproduction:
  1. Open `http://localhost:3000/webhooks` (or `/`) in the QA Chrome session.
  2. App stays on the centered spinner indefinitely.
  3. DevTools/Network shows `GET http://localhost:4000/v1/auth/setup-status` and `GET http://localhost:4000/v1/auth/me` stuck in `pending` for the full session (>60s observed; agent-8 retry timed out at this same point).
  4. Direct `curl http://localhost:4000/v1/auth/setup-status` returns 200 in ~5ms; `curl http://localhost:4000/v1/auth/me` (no cookie) returns 401 in ~1ms. So the API itself is healthy — only requests from this browser context hang.
  5. `javascript_tool` calls into the page eventually time out too ("renderer may be frozen or unresponsive"), suggesting the React tree is suspended on these queries and any new microtask piles up behind them.
- Expected: Auth bootstrap completes within ~1s, dashboard renders, /webhooks and /evals are usable.
- Actual: Requests never complete in this Chrome tab; nothing in the dashboard ever renders. Every QA route under `_dashboard` is unreachable.
- Console: only the standard Vite "[vite] connecting / connected" and the React DevTools tip — no JS errors, no fetch rejections (because the fetches never settle).
- Network: only two app-API requests, both `pending` indefinitely:
  - `GET http://localhost:4000/v1/auth/setup-status`
  - `GET http://localhost:4000/v1/auth/me`
  No `OPTIONS` preflights captured either, which is suspicious given these are cross-origin (3000 -> 4000).
- Suspected source: likely a CORS-credentials / cookie / preflight issue specific to the QA Chrome profile (the same handler that the previous Agent 8 attempt also stalled on, per the task description). Possibilities:
  - Backend never responds to the browser's preflight because the request includes `credentials: 'include'` from a `localhost:3000` origin and the in-flight server config rejects/hangs without responding (curl bypasses CORS entirely, hence the contradiction).
  - The frontend `Suspense`/router guard wraps these queries with no timeout and no error boundary, so a single hung auth call freezes the entire app shell.
  - File pointers to investigate (not opened in this session, names from the route-tree network log): `src/routes/_dashboard.tsx`, `src/routes/_auth.tsx`, and whatever query client wraps `/v1/auth/me` + `/v1/auth/setup-status` (search for those URL strings).

### [P2] No client-side timeout / error fallback on auth bootstrap
- Route: app shell (`_dashboard` route guard)
- Reproduction: see P1 above — same trigger.
- Expected: Even if the auth probe hangs, the UI should surface a "Couldn't reach API, retry" state within ~10s, not spin forever, so a user (or a QA bot) can recover.
- Actual: Indefinite spinner with no fallback, no toast, no error UI, and the renderer eventually freezes hard enough that even DevTools `Runtime.evaluate` times out.
- Console: none.
- Network: same two requests stuck in `pending`.
- Suspected source: the loader/guard for `_dashboard.tsx` (and likely the `useQuery` for `auth/me`) — needs an `AbortSignal.timeout(...)` + error boundary.

## Notes
- Cleanup status: no `qa-*` webhook created (could not reach /webhooks UI at all), nothing to clean up.
- No /evals testing was possible — all dashboard routes are gated on the same broken auth bootstrap.
- Backend API itself appears healthy (curl probes: `/health` 200, `/v1/auth/setup-status` 200, `/v1/auth/me` 401, `/v1/webhooks` 404 — note: the un-versioned/un-scoped `/v1/webhooks` 404 is expected if webhooks live under an org/collection path, but worth flagging in case the route isn't mounted at all).
- This is the second consecutive Agent 8 attempt to be blocked at exactly the same point per the task brief — the underlying P1 is reproducible and not transient.
