# Agent 3: Collection Home, Documents List, Document Detail

## Tested
- /collections/arxiv (collection home — redirects to documents)
- /collections/arxiv/documents (documents list — fully rendered, all 7 docs observed, all interactive refs captured)
- /collections/arxiv/documents/bb085a78-7123-4495-9fdb-6032c480264c (single doc detail — navigation worked, page never finished hydrating; see P2-doc-detail-never-loads)
- /collections/test/documents (navigation succeeded, but session was destroyed mid-test by another QA agent's logout; page never rendered after session loss — counted under P1-shared-session)
- Code path verification for routes I could not visually render against `app/src/routes/_dashboard.collections.$name.*` and `app/src/features/collections/documents-tab.tsx`

Test-environment context (same as Agent 1's report): 10 QA agents share one Chrome instance with persistent SSE streams against a single dev backend, so Chrome's 6-connection-per-origin cap repeatedly stalled fresh tabs at the layout spinner and at one point another agent logged out the shared admin session. Findings below were captured during the windows where rendering actually completed; behavioural bugs (vs. environment flakiness) are cross-checked against source.

## Issues

### [P1] /collections/$name has no "home" — just an immediate redirect with a misleading "Collection" page chrome
- Route: /collections/arxiv (and /collections/test)
- Reproduction:
  1. Navigate to `/collections/arxiv`
  2. Observe URL bar and rendered content
- Expected: Either a real collection landing page (overview/dashboard with name, embedding model, vector store, stat tiles, recent activity), OR if redirect-only behaviour is intentional, redirect should be instant and have no flash. The QA spec for this route explicitly asks me to verify "Header (name, embedding model, vector store, doc count)" and "Stat tiles match what overview shows" — neither exists.
- Actual: `app/src/routes/_dashboard.collections.$name.index.tsx` is a 30-line component that just renders a `<Spinner/>` and calls `navigate({ to: "/collections/$name/documents", replace: true })` in `useEffect`. The header, embedding-model badge, vector-store badge, and stat tiles (Documents/Chunks/Tokens/Storage) only render on the `/documents` child route via `_dashboard.collections.$name.tsx`. There is no collection home/overview at all.
- Console: none
- Network: none (purely a UX/architecture issue)
- Suspected source: `app/src/routes/_dashboard.collections.$name.index.tsx:9-20` (redirect-only component) and the parent shell `app/src/routes/_dashboard.collections.$name.tsx` that renders chrome only for the children.

### [P1] Documents tab persists a stale upload session ID in localStorage and hangs forever on "Loading upload session…"
- Route: /collections/arxiv/documents
- Reproduction:
  1. Open `/collections/arxiv/documents` in a tab where some prior session left `bigrag:upload-sessions` populated in localStorage (e.g. a previous upload session was cancelled, the backend purged it, or another browser/user finished it).
  2. Observe the area between the dropzone and the document list.
- Expected: If the session no longer exists on the backend (or returned 404), the stored sessionId should be cleared and the row should disappear — or the row should at least show an error like "Couldn't load upload session" with a Dismiss/retry control.
- Actual: A persistent `Spinner` + "Loading upload session…" card renders indefinitely while the rest of the page (dropzone, document list with 7 docs ready, stat tiles 7/103/11K/275.3 KB) loads normally around it. Observed live on `/collections/arxiv/documents` — the spinner sat there for the full 25+ seconds the tab survived; the document list loaded fine in parallel.
- Console: none (the SSE wrapper appears to swallow non-2xx; same pattern Agent 1 noted)
- Network: not captured for this specific request (tracking was started after the page had already begun loading), but the symptom matches "uploadSession.data is undefined while activeSessionId is truthy" branch
- Suspected source:
  - `app/src/features/collections/documents-tab.tsx:191-198` — renders the spinner card when `activeSessionId && !uploadSession.data`, with no error/timeout branch and no dismiss control.
  - `app/src/features/collections/upload-session-store.ts` — persists `activeSessionIds` in `localStorage` under `bigrag:upload-sessions` with no expiry / no "clear on 404" logic.
  - `app/src/hooks/use-documents.ts:72-89` — `useUploadSession` uses `useSseSnapshotQuery` with no `onError` / no automatic `clearActiveSessionId` on failure.

### [P1] Shared admin session was killed mid-session, taking all of my open dashboard tabs to /login with no graceful messaging
- Route: /collections/test/documents (active when it happened)
- Reproduction (not deterministic in the multi-agent harness but the pattern is real):
  1. Be on `/collections/test/documents` with a valid session.
  2. Another agent invokes logout (or session expires server-side).
  3. Existing dashboard tabs notice the 401 from a background SSE/query.
- Expected: A toast or banner ("Your session ended — please sign in again") and ideally an option to return to the same page after re-login. The login page itself should always render quickly.
- Actual: All 3 of my dashboard tabs bounced to `/login` simultaneously with no UI message. The `/login` page itself then sat on the layout spinner for 60+ seconds (likely connection-cap exhaustion from the other 9 agents' SSE streams — see Agent 1 P2-conn-exhaustion).
- Console: not capturable (renderer became unresponsive in all 3 tabs at the moment of redirect)
- Network: none capturable
- Suspected source:
  - `app/src/layouts/dashboard-layout.tsx:82-97` — `useDashboardAuthRedirect` silently navigates to `/login` on session loss; no toast / no "?from=…" return URL preserved.
  - `app/src/routes/_auth.login.tsx` likely also doesn't show a "you were signed out" banner.

### [P2] Document detail route never finishes loading from the documents list — page stays on layout spinner for 60+ seconds
- Route: /collections/arxiv/documents/bb085a78-7123-4495-9fdb-6032c480264c
- Reproduction:
  1. Open `/collections/arxiv/documents` (renders fine).
  2. Click the first document or directly navigate to `/collections/arxiv/documents/{docId}`.
- Expected: The detail page (metadata, file size, MIME, hash, chunk previews, Reprocess / Delete buttons) should render within a few seconds.
- Actual: The layout spinner kept spinning for 60+ continuous seconds across multiple wait cycles; `document.body.innerText` stayed at just "Skip to content"; the `<main>` never mounted. The route file `_dashboard.collections.$name.documents.$docId.tsx` references `useDocument`, `useChunks`, `usePlatformStats`, plus worker-status hooks — that's at least 4 concurrent requests on top of the layout's auth/session check. With the 6-connection-per-origin cap shared across 10 QA agents this route in particular seems to starve.
- Console: none (renderer froze under JS `fetch` introspection)
- Network: requests visible but stuck `pending` (same root cause as Agent 1's P2-conn-exhaustion)
- Suspected source:
  - `app/src/routes/_dashboard.collections.$name.documents.$docId.tsx:11-23` — `useDocument`, `useChunks`, `useReprocessDocument`, `usePlatformStats`, plus `WorkerOfflineBanner` (which itself reads stats) all fan out simultaneously without any batched/dependent loading.
  - Likely related to `app/src/hooks/use-sse-snapshot-query.ts` keeping SSE streams open and exhausting Chrome's 6-connection cap (Agent 1 P2-conn-exhaustion).

### [P2] Documents list is missing search, filter, sort, pagination, and bulk-action controls that the QA spec asks me to verify
- Route: /collections/arxiv/documents
- Reproduction:
  1. Open `/collections/arxiv/documents`
  2. Look for a search field, sort dropdown, filter chips, pagination controls, bulk-select checkboxes, or "Reprocess all"/"Delete selected" actions.
- Expected: At minimum a search-by-filename field and a sort (date/name/status). For the `test` collection (43 docs) pagination is essential — without it users will hit `useDocuments`' default limit and have a truncated UI with no way to advance.
- Actual: The DocumentsTab renders only a dropzone, an upload-session card, and a flat `<ul>` of documents. The only controls per row are the file link and a Delete (trash) icon. The header row only has Filename / Size / Chunks / Updated columns and no sortable affordances. There is one passive "Showing newest N of TOTAL documents" line when truncated (line 220-223) but no UI to load more / paginate. No bulk select. No filter. No search. No status column (status shows as a dot+badge under the filename only).
- Console: none
- Network: none
- Suspected source: `app/src/features/collections/documents-tab.tsx:210-272` — the entire list rendering. `useDocuments(name)` in `app/src/hooks/use-documents.ts` is presumably called with no pagination params.

### [P2] Collection chrome shows badges with no labels, so "1536d" / "turbopuffer" / "text-embedding-3-small" read as a row of cryptic pills
- Route: /collections/arxiv/documents
- Reproduction:
  1. Open `/collections/arxiv/documents`
  2. Look at the badges to the right of the collection name.
- Expected: Each badge has a small caption (e.g. "Embedding: text-embedding-3-small", "Vector store: turbopuffer", "Dimensions: 1536"), or at least an `aria-label`/title attribute so screen readers and tooltip-hovers explain the value.
- Actual: Three bare-text badges in a row with no preceding label and no hover/tooltip. A first-time user cannot tell which value is which from the UI alone.
- Console: none
- Network: none
- Suspected source: `app/src/routes/_dashboard.collections.$name.tsx` (parent shell that renders the collection name + meta badges).

### [P3] Status pill in document row is muted to the point of being easy to miss; "ready" is the only state I could observe
- Route: /collections/arxiv/documents
- Reproduction:
  1. Open `/collections/arxiv/documents`
  2. Look at the status pill underneath each filename.
- Expected: A more prominent state representation — at minimum its own column so users can scan-sort by status, especially when looking for the 1 failed doc that's supposed to exist somewhere in the system.
- Actual: Status is a small `Badge dot` rendered inline below the filename. All 7 arxiv docs were `ready` (green dot). I never reached `/collections/test/documents` to find the failed doc the spec describes — the dev environment lost my session before the page rendered.
- Console: none
- Network: none
- Suspected source: `app/src/features/collections/documents-tab.tsx:240-247` — Badge is rendered inside the filename column rather than as its own grid column; no list view in `_dashboard.collections.$name.documents.tsx` lets the user filter to `failed`.

### [P3] "Loading upload session…" card and the document list's "isPending" spinner can both show at the same time during a hard reload, doubling the spinners
- Route: /collections/arxiv/documents
- Reproduction:
  1. Hard-reload `/collections/arxiv/documents` on an account with a persisted upload session
  2. Observe the page for the first ~5 seconds
- Expected: One unified loading state, or the upload-session row should be subordinated to a corner of the list header.
- Actual: A full-width "Loading upload session…" card appears mid-page and a separate centered spinner appears below it while documents fetch — captured in screenshot ss_5312xb0jl and the rendered text "Loading upload session…" alongside the lower spinner before docs hydrated.
- Console: none
- Network: none
- Suspected source: `app/src/features/collections/documents-tab.tsx:191-203` — the `activeSessionId && !uploadSession.data` block and the `isPending` block are independent siblings with no coordination.

## Notes
- **Collection arxiv** stats observed: Documents 7, Chunks 103, Tokens 11K, Storage 275.3 KB; embedding `text-embedding-3-small`, vector store `turbopuffer`, dims `1536d`. Subnav: Documents (7) / Connectors / Search / Settings. All four nav links are present as `<a href>`; only Documents was clicked through to during my session.
- **Collection test** could not be visually verified — multi-agent contention prevented the page from rendering after my session was destroyed. The 1 failed document the spec describes therefore couldn't be located through the UI; based on code review the failed state would render as `Badge dot variant="error"` with an `error_message` shown as truncated red text next to it (`documents-tab.tsx:244-246`), and the detail page would render with `statusVariant.failed = "error"`. No visible filter to find it.
- Document IDs captured from arxiv (in case useful for other agents):
  - bb085a78-7123-4495-9fdb-6032c480264c (GSTR1_29AYKPY4219R2Z7_042026.pdf, 52.9 KB, 24 chunks)
  - b5c06bb0-ee92-43ac-8561-623ed5e9c8ba (GSTR3B_29AYKPY4219R2Z7_032026.pdf, 38.8 KB, 10 chunks)
  - 24a2b104-1632-48fa-9d0b-f18db8e2797e (GSTR1_29AYKPY4219R2Z7_032026.pdf, 53.0 KB, 24 chunks)
- "All collections" back link in the page header works (`href="/collections"`); subnav links also work (`/collections/arxiv/{documents,connectors,search,settings}`).
- Upload dropzone shows correct allowed types in the helper text ("PDF, DOCX, PPTX, MD, HTML, TXT, images") and `Files` / `Folder` buttons; per the spec I did NOT click them to actually trigger an upload.
- Per-row Delete (trash) buttons present; not clicked.
- Reprocess button noted in source for the detail page (`RefreshCcw` icon, `useReprocessDocument` hook) but could not visually verify since the detail page never rendered for me.
- Download-original button not visible in the document-detail source I read (would expect a `download_url` field on the API response or a route under `/v1/collections/{name}/documents/{id}/download`); none referenced in `_dashboard.collections.$name.documents.$docId.tsx`. Could not confirm via UI.
