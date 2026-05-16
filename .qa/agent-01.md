# Agent 1: Overview & Global Layout

## Tested
- /overview (initial load + reloads)
- /collections (via overview "New collection" button)
- /overview (return navigation)
- User menu (opened, did not log out)
- Sidebar link inventory (no full per-link navigation due to test-environment connection exhaustion described in P2-conn-exhaustion below)

Browser test environment context: 10 QA agents share one Chrome instance against a single dev backend on HTTP/1.1. Chrome's hard cap of 6 connections per origin combined with the app's multiple long-lived SSE streams (see P2-conn-exhaustion) made many of my reload attempts hang on the initial spinner. The findings below were captured during the windows where the page actually rendered.

## Issues

### [P2] Realtime SSE endpoints intermittently return HTTP 503; UI silently retries instead of surfacing a degraded state
- Route: /overview
- Reproduction:
  1. Load /overview while the backend's readiness cache reports a non-"ok" status (or while several admin tabs/agents are open)
  2. Watch DevTools Network for `/v1/admin/realtime/platform/stats`, `/v1/admin/realtime/platform/readiness`, `/v1/admin/realtime/access/overview?window_days=7`
- Expected: Either a successful SSE stream, or a visible "metrics unavailable" / "service degraded" message in the affected panels so the operator knows the dashboard is stale.
- Actual: All three SSE endpoints returned `503` repeatedly during my session (captured multiple times across reloads). The UI just keeps showing the "checking" pill on System Health, "0% ready" on Document Readiness, and a loading spinner where stats should be — with no error toast, no banner, no retry indicator, no message.
- Console: No console errors (the SSE wrapper appears to swallow non-2xx responses).
- Network: Repeated `GET /v1/admin/realtime/platform/stats 503`, `…/platform/readiness 503`, `…/access/overview?window_days=7 503`.
- Suspected source: `app/src/hooks/use-sse-snapshot-query.ts` (SSE wrapper used by `usePlatformStats`/`useReadiness`/`useAccessOverview`) is not surfacing the 503 to the consumer; backend side: `api/bigrag/routers/health.py:199` returns 503 when the cached readiness status is not "ok", and `api/bigrag/routers/admin_realtime.py:524-554` re-emits that result through the realtime stream.

### [P2] Loading state of overview shows misleading concrete values instead of skeletons
- Route: /overview
- Reproduction:
  1. Hard-reload /overview
  2. Observe the page during the few seconds (or longer when SSE is degraded) before stats and collections data hydrate
- Expected: Skeleton placeholders, or at minimum labels that distinguish "no data yet" from "loading".
- Actual: While loading, the page renders:
  - Collections card: spinner above, sub-label "0 visible in the admin UI" (looks like a real "you have zero collections" message)
  - Documents card: "0 ready, 0 queued" sub-label (looks like a real "queue is empty" message)
  - Storage card: "0/5 services online" sub-label (looks like a critical outage)
  - Document readiness: green "0% ready" badge and Ready/Processing/Pending/Failed all `0` (looks like "no documents")
  - Ingestion queue: "Queue is clear" status text (looks like everything is healthy when in fact we have no data yet)
  - System health: pills say "checking" but the stat cards above don't
- Console: none
- Network: none (this is purely a render-state issue)
- Suspected source: `app/src/features/overview/overview-page.tsx` lines 107-136 — sub-labels are computed from `collections.length`, `docs?.ready ?? 0`, `servicesOnline`, etc. without distinguishing `undefined`/`pending` from `0`. Same pattern in the Ingestion queue panel which renders "Queue is clear" when `queueItems` happens to be empty *or* when stats haven't arrived yet.

### [P2] "Collections" stat card and "X visible in the admin UI" sub-label come from two different sources and disagree
- Route: /overview
- Reproduction:
  1. Open /overview with the `/v1/collections?limit=200` request slow or 5xx and `/v1/admin/realtime/platform/stats` returning data
  2. The top number reads "2" (from `platform_stats`), the sub-label reads "0 visible in the admin UI" (from the still-loading collections list)
- Expected: Either pull both numbers from the same source, or keep them in sync, or show a spinner in the sub-label until both have resolved.
- Actual: Captured screenshot shows `Collections: 2 / 0 visible in the admin UI` — confusing and looks like an RBAC bug.
- Console: none
- Network: `/v1/admin/realtime/platform/stats` 200, `/v1/collections?limit=200` pending
- Suspected source: `app/src/features/overview/overview-page.tsx:107-112` — `value` derives from `stats?.collections`, but `sub` derives from `collections.length` (a different query). The two queries finish at different times.

### [P2] Document readiness vs. Ingestion queue numbers are wildly inconsistent on the same screen
- Route: /overview
- Reproduction:
  1. Load /overview when both data sources have hydrated
- Expected: Both panels should agree, or each should clearly explain it counts something different.
- Actual: Document readiness reports `49 ready / 0 processing / 0 pending / 1 failed`, Ingestion queue reports `Queued 506 / Completed 179 / Failed 42 / Dead Lettered 42`. As an operator I cannot tell whether there are 0 or 506 items waiting, and whether there are 1 or 42 failures. Neither panel explains the difference (documents vs. jobs).
- Console: none
- Network: data comes from `/v1/admin/realtime/platform/stats` (single source); the inconsistency is in how the same payload is rendered into the two panels.
- Suspected source: `app/src/features/overview/overview-page.tsx` — `docs?.failed` and `stats?.queue?.failed` are used side-by-side without labels explaining the units.

### [P2] "Ingestion queue" surfaces "degraded — Dead-lettered jobs need operator review" but offers no link to act on it
- Route: /overview
- Reproduction:
  1. Open /overview
  2. Scroll to Ingestion queue panel; observe `degraded` pill and "Dead-lettered jobs need operator review."
  3. Try to click the message or the "42" beside Dead Lettered
- Expected: The panel should link to a queue / dead-letter / failed-documents view so the operator can act.
- Actual: The warning is purely informational; nothing on the panel is clickable. There is no /queue or /dead-letter route in the sidebar that I could find.
- Console: none
- Network: none
- Suspected source: `app/src/features/overview/overview-page.tsx` ingestion queue Panel — needs a `<Link to="/...">` wrapper on the row or a "Review" action button.

### [P2] "1 Failed" document on Document Readiness card is a count with no drilldown
- Route: /overview
- Reproduction:
  1. Look at Document Readiness card — Failed shows `1` against a red dot
  2. Try to click the `1` or the "Failed" label
- Expected: Click should navigate to the failed document(s), or at least to a filtered Documents list.
- Actual: Nothing is clickable. There is also no toast/notification linking to this elsewhere.
- Console: none
- Network: none
- Suspected source: `StatusCount` component used in `app/src/features/overview/overview-page.tsx:162-165` is non-interactive.

### [P3] "New collection" button on overview navigates to /collections list page instead of opening a creation form
- Route: /overview
- Reproduction:
  1. Click "New collection" in the header (top-right of /overview)
- Expected: Either open a modal/drawer with the new-collection form, or land directly on /collections/new (or focus the "New collection" button on /collections). Most dashboard products with a "Create" CTA take the user straight to creation, not to a list page.
- Actual: Routes to `/collections` (the listing page). The user then has to find and click another "New collection" button at the top of /collections. Two extra steps for what looks like a one-click action.
- Console: none
- Network: none
- Suspected source: `app/src/features/overview/overview-page.tsx:102` — `<PillLink to="/collections" … label="New collection" primary />` should point to a creation route or trigger a modal.

### [P3] SSE connection design exhausts Chrome's 6-per-host connection pool, blocking simple XHR for tens of seconds
- Route: /overview (and any other page that opens multiple realtime streams)
- Reproduction:
  1. Open 3-4 admin tabs in the same browser (or one tab on a page that opens several SSE streams)
  2. Watch `/v1/auth/me`, `/v1/auth/setup-status`, `/v1/collections?limit=200` stall in "pending" for 20-60s while curl against the same backend returns in < 10ms
  3. `lsof -i :4000` confirms 6 Google Chrome ESTABLISHED sockets (the per-origin HTTP/1.1 cap)
- Expected: Either enable HTTP/2 on the backend (multiplexes streams over a single connection), or consolidate the multiple per-page SSE streams (`platform/stats`, `platform/readiness`, `access/overview`, plus per-collection stats and per-route streams) into a single multiplexed stream, so plain XHR isn't starved.
- Actual: With even modest multi-tab admin use, the overview's own follow-on requests (`/v1/collections`, `/v1/admin/embedding-presets`) sit in "pending" because every socket is held by an SSE stream. The user sees a near-blank spinner for ~30-60s.
- Console: none (the requests don't fail, they just don't start)
- Network: many `pending` requests against `localhost:4000`, while the same requests via curl complete in 1-8 ms
- Suspected source: `api/bigrag/main.py` (uvicorn config — no HTTP/2), and the spread of SSE endpoints in `api/bigrag/routers/admin_realtime.py` consumed by `app/src/hooks/use-sse-snapshot-query.ts`. Worth at minimum gating the number of concurrently-open SSE streams per page.

### [P3] User menu only contains "Sign out"
- Route: /overview (global)
- Reproduction:
  1. Click the user button at the bottom-left of the sidebar (shows "Yoginth / yoginth@hey.com")
- Expected: Account settings, profile, theme, keyboard shortcuts, "what's new", etc. — typical SaaS account menu items.
- Actual: A single "Sign out" item. The same email is already shown on the sidebar trigger, so opening the menu only serves logout.
- Console: none
- Network: none
- Suspected source: `app/src/components/navigation/sidebar.tsx` — user popover menu.

### [P3] No theme toggle anywhere in the layout
- Route: /overview (global)
- Reproduction:
  1. Look for a theme/appearance toggle in the header, sidebar, user menu, or /settings
- Expected: At minimum a light/dark/system toggle is standard for dashboards in 2026.
- Actual: None present. `document.documentElement.classList.value === ""`. No `dark:` classes in `app/src/components/**`. Page is hard-coded light.
- Console: none
- Network: none
- Suspected source: missing — needs a ThemeProvider plus toggle (e.g. in the user menu or sidebar footer).

### [P3] Access telemetry "P95 latency 4,423 ms / 1,710 ms average" is shown raw without a goal/threshold
- Route: /overview
- Reproduction:
  1. Look at the Access telemetry panel after data loads
- Expected: A target line, color coding, or trend arrow so the operator knows whether 4.4s P95 is acceptable. As-is it is just a number.
- Actual: Just text. There is no SLO line and no comparison to last period. (4.4s P95 is also suspiciously high for an admin dashboard's own queries, but without trend context it is hard to know whether to act.)
- Console: none
- Network: none
- Suspected source: `app/src/features/overview/*` access telemetry panel — needs a "good/warn/bad" threshold and/or trend.

### [P4] "Access health 100.0%" pill jumped to "97.9%" while user menu was open (live refresh)
- Route: /overview
- Reproduction:
  1. Load /overview, wait for Access telemetry to render
  2. Open the user menu (or simply wait ~15-30s)
- Expected: Live updates are fine, but the value should animate, not jump from `100.0%` to `97.9%` and from `46 → 47` events with no visual cue that "this just refreshed."
- Actual: The numbers replace in place with no transition or "updated just now" indicator.
- Console: none
- Network: SSE pushes new snapshot
- Suspected source: stat cards lacking a transition on value change.

### [P4] Header button "Open navigation" exists in the DOM with no visible target
- Route: /overview (desktop viewport)
- Reproduction:
  1. `document.querySelector('button[aria-label="Open navigation"]')` returns a hidden button
- Expected: At desktop sizes this button is correctly hidden, so this is more of a heads-up than a bug. Make sure it has visible focus styles and a sensible label when it does appear on mobile (I did not test responsive widths).
- Console: none
- Network: none

### [P4] No `Skip to content` visible focus state
- Route: /overview
- Reproduction:
  1. `Tab` once when /overview is focused — `Skip to content` appears in the accessibility tree text dump
- Expected: Skip link should be visually presented when focused (it may already be — I could not Tab-test reliably because the page kept entering a perpetual loading state during my session).
- Actual: Could not confirm visibility on focus due to environment instability.

## Notes

- Header user-name greeting "Good to see you, Yoginth" works (uses `display_name`).
- Stat cards all rendered real numbers on the one successful load: `Collections 2 / Documents 50 / Chunks 6,027 / Tokens stored 607K / Storage 103.5 MB`. System Health pills all read "online" (`Postgres / Vector store (per collection) / Redis / Embeddings / Worker`).
- All 5 service rows in System Health correctly rendered after data hydration; the Vector store label correctly includes the provider name ("per collection" in our case).
- All sidebar links use real `href`s and `@tanstack/react-router` `<Link>` (no full reloads): `/overview /collections /models /chat /evals /mcp /api-keys /webhooks /connectors /access-logs /usage /audit /backups /vector-storage /settings`. I could not click through every one due to environment instability, but the link structure looks sane and the route files exist in `app/src/routes/_dashboard.*.tsx`.
- "Ask bigRAG" link correctly points to `/chat`.
- Quick-action footer cards (`Run a query → /chat`, `Manage collections → /collections`, `Mint API key → /api-keys`) all wired up correctly.
- No `<img>` without `alt` on the page. No `<button>` without text or `aria-label`. `<html lang="en">` set. Page title is "bigRAG".
- 28 focusable elements on the page (sidebar + header + cards + ingestion queue + quick actions).
- The "Open logs" → `/access-logs` and "View all" → `/collections` shortcuts in cards are correctly typed as links with href, so middle-click / cmd-click works.
- Test-environment caveat: because of the connection-exhaustion problem (P3 above), I was unable to systematically click through every sidebar link, reach the "click into arxiv and test" step, or reliably observe Recent Collections card hydration. The card was stuck on its spinner during all post-first-load visits. I would recommend re-running this agent in isolation (or against an HTTP/2 backend) to get the rest of the navigation coverage.
