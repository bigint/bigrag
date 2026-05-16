# Agent 9: Models, Vector Storage, Backups

## Tested
- /models  (Embedding presets tab, Runtime settings tab, New preset modal)
- /vector-storage  (Qdrant tab, turbopuffer tab)
- /backups  (page never finished rendering — see P1 below)

## Issues

### [P1] Backups page never renders — stuck on loading spinner indefinitely
- Route: /backups
- Reproduction:
  1. Navigate to http://localhost:3000/backups while logged in as admin.
  2. Wait 60+ seconds; only the loading spinner is visible (no header, no nav, no content).
- Expected: Backups page renders with PageHeader "Backups", description, "Backup runbook" section (Destination/Validation/Export steps), Instance Settings (backups group), "Readable backups" card with start-backup form, warning about readable backups, and history table or empty state, per `app/src/features/backups/backups-page.tsx`.
- Actual: Page renders only the spinner; `useBackups`, `useInstanceSettings`, and `usePlatformStats` queries never resolve in the browser.
- Console: No errors logged; only Vite connect / React DevTools info messages.
- Network: route bundle (`/src/routes/_dashboard.backups.tsx`, `/src/features/backups/backups-page.tsx`, `/src/hooks/use-backups.ts`) all fetched 200 from Vite. `/v1/auth/me` and `/v1/auth/setup-status` requests issued from this tab go pending forever (never reach `statusCode: 200`), and no `/v1/admin/backups` request is ever fired. From CLI, `GET /v1/admin/backups` returns `401` in ~2ms, so the API itself is healthy — the hang is browser-side. Tabs hammered with concurrent QA traffic exhausted the per-origin HTTP/1.1 connection pool to `localhost:4000`; once `auth/me` stays "pending", every downstream page that gates on auth (Backups, Vector Storage, Models) never gets past the spinner.
- Suspected source: `app/src/lib/api-client.ts` / auth context — `useAuth` blocks rendering until `/v1/auth/me` resolves, and stale pending auth requests are not cancelled or short-circuited, so the page deadlocks instead of failing or retrying. Frontend should set a request timeout, dedupe concurrent `auth/me` calls, or use AbortController on stale fetches.

### [P1] POST /v1/admin/embedding-presets hangs from the browser (Vite dev) — modal "Create preset" never finishes
- Route: /models  ("+ New preset" modal)
- Reproduction:
  1. /models → "+ New preset"
  2. Fill Name (e.g. `qa-9-model-1715850000`), leave Provider=OpenAI, Model=text-embedding-3-small, fill API key with placeholder, click "Create preset".
  3. Reproduced again from devtools: `fetch('http://localhost:4000/v1/admin/embedding-presets', {method:'POST', credentials:'include', body: JSON.stringify({name, provider:'openai', model:'text-embedding-3-small', api_key:'sk-x', dimension:1536})})` — preflight OPTIONS returns 204, then POST goes pending and never completes.
- Expected: 200/201 response, modal closes, new row appears in the presets table.
- Actual: POST stays `pending` indefinitely; modal never closes. From CLI/curl, the same POST returns `401 in ~2ms` without auth, so the API responds quickly — the hang is again on the browser side, in the same connection-pool/auth deadlock as the Backups bug. Result: a user clicking "Create preset" cannot tell whether the preset was created; no spinner timeout, no error toast, no retry.
- Console: none.
- Network: `OPTIONS /v1/admin/embedding-presets` → 204; `POST /v1/admin/embedding-presets` → pending forever; concurrent `GET /v1/auth/me` also pending.
- Suspected source: same auth-pending deadlock as the Backups issue; additionally, the embedding-presets mutation hook needs a per-request timeout / AbortController so the UI can surface the failure to the user. Mutation likely in `app/src/hooks/use-embedding-presets.ts` (or equivalent under `app/src/features/models/`).

### [P2] /models page wedges on "Loading presets..." after navigating away and back
- Route: /models
- Reproduction:
  1. Open /models (loads ~15s, presets render).
  2. Navigate away, then return to /models in the same tab.
  3. Spinner with "Loading presets..." stays visible indefinitely; existing preset row never reappears.
- Expected: Presets reload within a couple seconds (`GET /v1/admin/embedding-presets` already returned 200 on first load).
- Actual: Second fetch returns 200 but UI does not update; spinner persists. Direct devtools `fetch('http://localhost:4000/v1/admin/embedding-presets', {credentials:'include'})` returns the JSON instantly with `{"presets":[{"id":"d7f6af56-...","name":"Test","provider":"openai","model":"text-embedding-3-small","base_url":null,"dimension":1536,"has_api_key":true,...}],"total":1}` — so the data is available; the React Query state is just not flushed back into the page.
- Console: none.
- Network: `GET /v1/admin/embedding-presets` 200 OK both times; `GET /v1/auth/me` pending.
- Suspected source: likely the same auth-pending suspense gating in the models page wrapper, or a `useQuery`/`useSuspenseQuery` shaped to wait on `auth/me` before considering presets "loaded". Files: `app/src/features/models/*` and `app/src/hooks/use-embedding-presets.ts`.

### [P2] /vector-storage page slow-to-load (Qdrant tab) — ~30s until first paint
- Route: /vector-storage
- Reproduction: open /vector-storage from a fresh tab.
- Expected: Render within a few seconds.
- Actual: "Loading settings..." for ~30s before Qdrant settings finally appear. Same auth-pending stall as elsewhere; once auth resolves the page populates correctly (Qdrant URL default `http://localhost:6333`, Qdrant connect timeout default 10, Require vector store toggle, Qdrant search ef "Optional, e.g. 128"; turbopuffer tab: API key shown as "Saved" placeholder, region default `aws-us-east-1`, namespace prefix default `bigrag_`).
- Console: none.
- Network: `GET /v1/admin/settings` eventually 200; many `auth/me` pending in the meantime.
- Suspected source: same auth-pending issue.

### [P3] /vector-storage shows only credentials forms — no per-collection routing, no storage stats, no health status
- Route: /vector-storage
- Reproduction: load the page, look at both Qdrant and turbopuffer tabs.
- Expected (per QA spec): per-collection routing table (which collection uses which backend), chunk/MB-used stats per backend, online vs degraded health indicator.
- Actual: Vector Storage page is purely a settings form (Qdrant connection / turbopuffer credentials). No routing display, no usage stats, no live health/status indicator on this page.
- Note: This may be intentional product scope rather than a bug — flagging as P3 because it diverges from the QA test spec and from what an operator would typically expect on a "Vector Storage" administration screen.
- Suspected source: `app/src/features/vector-storage/vector-storage-page.tsx` — feature is currently settings-only; routing/stats live elsewhere (likely in collection settings) or are not implemented.

### [P3] /models "New embedding preset" modal — validation errors are silent (red ring only, no message)
- Route: /models  ("+ New preset")
- Reproduction: open modal, leave Name and Provider API key empty, click "Create preset".
- Expected: clear, accessible error message identifying which fields are required (e.g. "Name is required", "API key is required") — ideally via `aria-describedby` so screen readers surface them.
- Actual: only a red border appears on the empty fields; no text, no toast, no aria error. A user who isn't watching closely won't know what's wrong.
- Suspected source: `app/src/features/models/*` preset create modal — Zod/RHF errors are being applied to ring color only.

### [P3] /models — no "Test connection" affordance on the preset create/edit modal
- Route: /models  (modal "New embedding preset")
- Reproduction: open modal.
- Expected (per QA spec): a "Test connection" button that calls the provider with the entered key and shows success/failure.
- Actual: form has only Name / Provider / Model / API key / Embedding dimension and Cancel / Create preset. There is no "Test connection" affordance anywhere on the modal or on the row actions (only edit pencil and trash).
- Suspected source: `app/src/features/models/*` preset modal — feature missing or never built.

### [P3] /models page is "Embedding presets" only — no rerank or chat provider presets
- Route: /models
- Reproduction: load /models; only "Embedding presets" and "Runtime settings" tabs visible. Provider dropdown lists only OpenAI, Cohere, Voyage AI; no `openai_compatible` (no Base URL field).
- Expected (per QA spec): saved embedding/rerank/chat provider presets, with `openai_compatible` provider needing a base URL.
- Actual: Models page covers embedding presets only; chat/rerank defaults live under Runtime settings → Chat defaults (Open) / Embedding and search sections. Reranker is not configurable as a preset.
- Note: Likely intentional product scope. Flagging because it diverges from the QA spec.

## Notes
- Cleanup status: no qa-* preset was created (POST hung — see P1 above), so there is nothing to delete. Verified the existing presets list still contains only the pre-existing "Test" preset via direct API check.
- No destructive backup, restore, or download action was attempted. The Backups page never rendered, so no buttons (start, restore, download) could be exercised through the UI.
- No vector-storage config was modified. Tabs were inspected read-only; "4 changed" badge on Qdrant and "3 changed" badge on turbopuffer were already present on first load (likely from a prior QA agent) — I did not click "Save changes".
- All three pages in scope share the same root cause for being slow/stuck: `GET /v1/auth/me` requests pile up `pending` in the browser tab, blocking auth-gated rendering. API endpoints themselves respond in low milliseconds when probed via curl. Fix recommendation: dedupe and timeout `auth/me`, and cancel stale fetches with AbortController.
- Runtime settings tab (in /models) does load and shows a structured form: RETRIEVAL → Embedding and search (Embedding concurrency, Default embedding provider/model/dimension/base URL/API key, "1 missing" badge, Advanced controls "3 settings", "1 secrets" indicator, Save changes); ANSWERING → Chat defaults (collapsed, Open to expand).
