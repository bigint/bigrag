# Agent 4: Per-Collection Search

## Tested
- /collections/arxiv/search
  - "summary" (Semantic, top_k=5) -> 5 results (eventually, after ~90s under load)
  - empty query -> validates client-side (button disabled)
  - 640-char "lorem ipsum…" query (Semantic) -> server returned 503 after ~90s, UI silently reset
  - "tax" with Keyword mode -> hung, eventually 400 then pending while server was overloaded
  - mode dropdown opened: Semantic / Keyword / Hybrid all present
- /collections/test/search
  - Never finished initial load — `GET /v1/auth/me` and `GET /v1/auth/setup-status` stuck pending for >60s
    while the page kept showing only the global loading spinner. No `/v1/collections/test` request was
    ever issued. The dashboard layout is gated on the auth bootstrap, so the search UI never appeared.
  - Could not exercise queries / modes / top-k / filters on `test` because the page never rendered.

Note: parallel QA agents were hammering the same `localhost:4000` instance, so the API was visibly
overloaded throughout this run (many `503`s, very long latencies, occasional `pending` forever).

## Issues

### [P2] Query errors are silently swallowed — no toast / no inline error
- Route: /collections/arxiv/search
- Query: "summary" (Semantic) and 640-char "lorem ipsum…" (Semantic)
- Reproduction:
  1. Run any query while the API is loaded/struggling (here other agents caused 503s).
  2. The `POST /v1/collections/<col>/query` returns 503 after ~90s.
  3. The button spinner stops and reverts to "Run query".
- Expected: A toast (or inline error under the input) explaining what went wrong, similar to other
  mutations in the app that go through `errorToast` (`src/lib/mutation-toast.ts`).
- Actual: No feedback at all. Previous results are gone, no new results, no error. The user has no
  way to know the request failed.
- Console: none
- Network: `POST http://localhost:4000/v1/collections/arxiv/query -> 503` (body empty)
- Suspected source: `app/src/hooks/use-query.ts:21-25` — `useRunQuery` has no `onError`. The mutation
  is consumed in `app/src/routes/_dashboard.collections.$name.search.tsx:31-39` without an
  `onError` either. Compare with other mutations that wire `errorToast(...)` from
  `app/src/lib/mutation-toast.ts`.

### [P3] No request timeout / loading indicator beyond a tiny button spinner
- Route: /collections/arxiv/search
- Query: anything heavy or while API is overloaded
- Reproduction:
  1. Click Run query. The only loading affordance is a small spinner inside the submit button.
  2. With Semantic search the request took ~90s end-to-end in this environment; nothing on the page
     hints at progress, "still working…", or a timeout.
- Expected: Either a longer-running progress hint (e.g. fade existing results into a skeleton, show
  elapsed time, or surface "this is taking longer than usual"), and/or an abort/retry control.
- Actual: Tiny spinner only; the user cannot tell whether anything is happening or whether the
  request will ever return.
- Console: none
- Network: `POST .../query` pending for ~90s before resolving 200/503.
- Suspected source: `app/src/routes/_dashboard.collections.$name.search.tsx:120-130` and `app/src/lib/api.ts`
  (no client-side timeout on the mutation).

### [P3] No client-side max-length / sanity check on the query input
- Route: /collections/arxiv/search
- Query: 640-char "lorem ipsum…" string
- Reproduction:
  1. Paste a 600+ char string into "Ask a question of this collection…".
  2. Click Run query.
  3. Request is sent verbatim and is treated the same as a normal query; under load it returned 503
     (see P2). There is no `maxLength`, no warning, no truncation, no character counter.
- Expected: Either a `maxLength` / counter / warning, or an explicit server validation message that
  surfaces in the UI. The validator in `collection-form-state.ts` only checks "non-empty".
- Actual: Long strings submit silently and then hit the same silent-503 path as P2.
- Console: none
- Network: `POST .../query` (1080-byte body) -> 503 after ~90s
- Suspected source: `app/src/features/collections/collection-form-state.ts`
  (`validateCollectionSearchFormValues`) — does not enforce a sane max length.

### [P3] Result link drops the chunk index (`#23` in label, but URL ignores it)
- Route: /collections/arxiv/search
- Query: "summary"
- Reproduction:
  1. Run "summary".
  2. Each result is rendered as `bb085a78#23` (docId + chunk index).
  3. Hovering / clicking the link goes to
     `/collections/arxiv/documents/bb085a78-7123-4495-9fdb-6032c480264c` — the chunk index is not
     preserved in the URL, so the document page can't scroll/highlight the matching chunk.
- Expected: Either a URL hash / query param (e.g. `?chunk=23` or `#chunk-23`) so the document page
  can deep-link to the chunk, or the label should not advertise `#23` if it's purely cosmetic.
- Actual: The `#23` part of the label is visual only; the destination opens the whole document.
- Suspected source: `app/src/routes/_dashboard.collections.$name.search.tsx:154-162` —
  `<Link to="/collections/$name/documents/$docId">` with no `search`/`hash` for the chunk.

### [P3] Result card does not surface page number or any source metadata
- Route: /collections/arxiv/search
- Query: "summary"
- Reproduction:
  1. Each result card shows: `score X.XXX` badge, `docId#chunk` link, snippet text.
  2. There is no page number, no document title / filename, no source URL — just an 8-char doc-id
     prefix. To find out which document a result is from the user has to click through.
- Expected: At minimum the document title/filename, plus page number when available (see spec).
- Actual: Only an 8-char hash prefix is shown.
- Suspected source: `app/src/routes/_dashboard.collections.$name.search.tsx:149-167` —
  it consumes only `r.id`, `r.score`, `r.document_id`, `r.chunk_index`, `r.text`, ignoring any
  other fields returned by the API (e.g. document title / page metadata).

### [P3] Mode dropdown options invisible until the panel finishes laying out
- Route: /collections/arxiv/search
- Reproduction:
  1. On first paint of the search form (before the collection stats above the tabs have loaded),
     click the Mode dropdown.
  2. Only the currently selected "Semantic" row renders text; "Keyword" / "Hybrid" rows exist in
     the DOM (queryable via `[role=option]`) but render blank in the popover.
  3. After the stats cards finish loading and the layout settles, opening the dropdown again shows
     all three labels normally.
- Expected: All three options should be readable from the first open.
- Actual: First open often shows only "Semantic" visually, even though Keyword / Hybrid options
  exist in the DOM and `textContent`. This was reproducible early in the session, then went away
  after the page fully stabilised, suggesting a hydration / layout race in the Select popover.
- Console: none
- Suspected source: Base UI `Select` popover in `app/src/components/ui/select.tsx` interacting with
  the page-shell skeleton/stats area above the form. Could not pin to a specific line.

### [P3] Test collection search page hangs on initial load when API is busy
- Route: /collections/test/search
- Reproduction:
  1. Navigate to `/collections/test/search` while the API is under heavy load.
  2. `GET /v1/auth/me` and `GET /v1/auth/setup-status` stay `pending` indefinitely.
  3. The page never renders the dashboard layout — it stays on the global circular spinner.
     `/v1/collections/test` and `/v1/collections/test/query` are never requested.
- Expected: Auth bootstrap should time out or fall back; a meaningful error should be shown so the
  user can retry instead of staring at a spinner forever. The collection page should not be 100%
  gated on `auth/me` succeeding instantly.
- Actual: Infinite loading spinner with no recovery path.
- Console: none
- Network: `GET .../auth/me` and `GET .../auth/setup-status` pending forever (other endpoints
  intermittently 503).
- Suspected source: Likely the auth bootstrap in `app/src/hooks/use-auth.ts` (and its consumer in
  the dashboard layout) — no timeout / no error fallback when these queries never settle.

### [P3] Double-submit possible on rapid clicks (saw 2 concurrent `/query` requests)
- Route: /collections/arxiv/search
- Reproduction: hard to repro cleanly under load, but after a click on Run query the network log
  showed two `POST .../query` `pending` entries simultaneously plus two `OPTIONS` preflights.
- Expected: The mutation should de-dup or the button should stay disabled until in-flight request
  finishes.
- Actual: The button does disable while `run.isPending`, so this may have been triggered by a stray
  click landing during a layout shift; worth confirming whether the mutation queue cancels
  in-flight requests when a new submit comes in.
- Suspected source: `app/src/hooks/use-query.ts` (no `mutationKey`) + button gating in the form.

## Notes
- Latencies (under heavy parallel-agent load):
  - `POST /v1/collections/arxiv/query` (Semantic, "summary", top_k=5): ~90s for the first
    successful 200; a re-run completed in ~10–20s once the queue drained.
  - `POST /v1/collections/arxiv/query` (Semantic, 640-char body): ~90s -> 503.
  - `POST /v1/collections/arxiv/query` (Keyword, "tax"): pending >30s, eventually 400 once (with a
    follow-up still pending when I moved on); could not get a 200 to confirm whether keyword
    results render differently from semantic.
  - `GET /v1/auth/me`, `GET /v1/auth/setup-status`, `GET /v1/admin/realtime/collections/*/stats`:
    intermittent `503` and long `pending` throughout — the API is being saturated by the parallel
    agents; this colours every other observation below.
- Search input autofocus on load: works (verified via `document.activeElement`).
- Placeholder text: "Ask a question of this collection…" — clear and on-brand.
- Top-K input: numeric `<input type="number">` with min=1, max=50; validates client-side (form
  schema 1–50). Could not verify the visual results-count change because of the silent-503 path
  blocking most reruns; the rendered count text ("5 RESULTS FOR \"summary\"") matches `top_k=5`.
- Reranking toggle: not visible on `arxiv` (`collection.reranking_enabled` is false). Could not
  exercise; correct conditional rendering at `_dashboard.collections.$name.search.tsx:106-119`.
- Filters: no metadata-filter UI on this page in the current build — the form schema supports
  `filters` (`use-query.ts`) but there is no field for it. Worth flagging as a missing feature vs
  the spec but not raising as a separate bug here.
- Could not compare same-query behaviour across `arxiv` vs `test` because the `test` page never
  loaded (P3 above).
