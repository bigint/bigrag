# Agent 2: Collections List & Create Flow

## Tested
- /collections (list)
- /collections (search filter, empty state)
- /collections/arxiv (row navigation)
- New collection modal (open / fields / dropdowns / cancel / X / re-open)
- Vector storage dropdown (Qdrant vs turbopuffer)
- Embedding preset dropdown (vs /v1/admin/embedding-presets)
- Field-level validation (empty name, spaces in name, chunk_overlap >= chunk_size)
- Cross-referenced /v1/collections?limit=200 payload

## Issues

### [P1] Empty name and invalid name pattern submit silently
- Route: /collections (New collection modal)
- Reproduction:
  1. Click "New collection"
  2. Leave Name empty, click Create collection
  3. Observe: Name input gets a red outline, but **no error message** appears anywhere; the "Lowercase letters, numbers, dashes and underscores." help text disappears so users have no idea what to fix
  4. Type "Bad Name With Spaces", click Create collection again
  5. Observe: Form submits a POST /v1/collections with the bad value
- Expected: Client-side validation matching the documented pattern; visible error text under the field
- Actual: Empty name -> red border only, no message; spaces submit goes through to API
- Console: none
- Network: POST /v1/collections fires with `{"name":"Bad Name With Spaces"}`
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:81-100 (only `value ? undefined : "Name is required"` validator; nothing checks the pattern, and the inline error doesn't render visibly because the help-text/error-text slot shares one line)

### [P1] Help text contradicts server validation pattern
- Route: /collections (New collection modal, Name field)
- Reproduction: Inspect the Name field help text vs the API schema
- Expected: Help text matches `^[a-zA-Z][a-zA-Z0-9_]*$` (letter start, alphanumeric + underscore, **no dashes**, mixed case allowed)
- Actual: Help text says "Lowercase letters, numbers, dashes and underscores." — dashes are NOT allowed by the API, mixed case IS allowed, must start with a letter (not a number)
- Console: none
- Network: A valid-per-helper-text name like `my-docs` would fail server-side with 422
- Suspected source:
  - UI: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:90
  - API: /Users/yoginth/bigrag/api/bigrag/models/collection.py:11 (`pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$"`)

### [P2] Form state persists after Cancel / X-close and reopen
- Route: /collections (New collection modal)
- Reproduction:
  1. Click "New collection"
  2. Type "Bad Name With Spaces" into Name
  3. Click Cancel (or the X close icon)
  4. Click "New collection" again
- Expected: Name field is empty (defaultValues applied on each open)
- Actual: Name still says "Bad Name With Spaces" — entire form keeps last state
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:30-42 — `form.setFieldValue("name","")` and other resets only run inside the **success** branch of `onSubmit`, never on `onClose`. The form instance lives across modal opens.

### [P2] Stuck "Creating…" state with no timeout / no error toast
- Route: /collections (New collection modal)
- Reproduction:
  1. Open modal, type any name, click Create collection
  2. If the API is slow / times out / returns 503, the button just stays "Creating…" forever
  3. Cancel button still works (closes the modal) but the in-flight mutation never surfaces an error to the user
- Expected: After a few seconds of pending or on non-2xx, show an error toast (errorToast hook exists in useCreateCollection) and re-enable the button
- Actual: Button stuck disabled at "Creating…" for 40+ seconds; even after closing and reopening modal, the button STILL says "Creating…" because the mutation is still pending and `create.isPending` is true (verified via DOM: `submitDisabled:true, submitBtn:"Creating…"`)
- Console: none
- Network: POST /v1/collections eventually returns 503 (under load); error toast never fires
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:206-208 + /Users/yoginth/bigrag/app/src/hooks/use-collections.ts:72 — `errorToast("Failed to create")` is wired but the modal also has its own `try/catch` in `onSubmit` that catches and toasts; the issue is no client-side timeout / abort, and the modal can be re-opened while the previous mutation is still pending

### [P2] Indefinite "Loading collections…" with no error on 503
- Route: /collections
- Reproduction:
  1. Navigate to /collections under any load that causes /v1/collections?limit=200 to return 503 (easy to reproduce — the page issues both /v1/collections and /v1/admin/embedding-presets in parallel; with multiple tabs open, several of these come back 503)
  2. Observe page sits on "Loading collections…" spinner forever
- Expected: Show an error state with retry option after the query errors
- Actual: Spinner persists indefinitely; `useCollections` query treats 503 as a retry-loop and never surfaces the error UI
- Console: none (the query layer eats errors)
- Network: GET /v1/collections?limit=200 → 503 (intermittent); subsequent retries also intermittently 503; the page only renders after a fully successful response
- Suspected source: /Users/yoginth/bigrag/app/src/hooks/use-collections.ts:19-24 — `useCollections()` has no `retry`/`onError`/error-UI fallback; the consuming route just shows the loading skeleton until `data` is set

### [P2] No client validation that chunk_overlap < chunk_size
- Route: /collections (New collection modal)
- Reproduction:
  1. Open modal, leave Chunk size = 512, set Chunk overlap = 1000, click Create
- Expected: Inline error before POSTing (the API enforces `chunk_overlap < chunk_size` in a model_validator at /Users/yoginth/bigrag/api/bigrag/models/collection.py:56-60)
- Actual: Form accepts the value and POSTs; user only finds out via a generic server error toast (and even that didn't fire reliably in our run — see P2 above)
- Console: none
- Network: would be 422 from server
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:181-200 (no cross-field validator)

### [P3] Inconsistent casing between vector-store options
- Route: /collections (New collection modal, Vector storage dropdown)
- Reproduction: Open dropdown
- Expected: Both options labeled consistently (e.g. "Qdrant" + "Turbopuffer")
- Actual: "Qdrant" (Capitalized) but "turbopuffer" (all-lowercase)
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:215-218 — `VECTOR_STORAGE_OPTIONS` literal

### [P3] Collections list "Storage" column reflects lowercase values inconsistently
- Route: /collections (list)
- Reproduction: View the table
- Expected: Provider labels rendered with consistent capitalization
- Actual: Storage badges show "turbopuffer" / "qdrant" (raw provider IDs, all lowercase) — matches the dropdown's "turbopuffer" but not the dropdown's "Qdrant"
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.index.tsx (list rendering passes the provider string as-is)

### [P3] "Actions" column has only a navigation arrow — no settings/delete/duplicate menu
- Route: /collections
- Reproduction: Look at the last column "Actions" — only an outward arrow icon that opens the collection
- Expected: Per row a kebab menu with Settings / Delete / Duplicate, OR rename the column to "Open"
- Actual: Single arrow; redundant with the row click (whole row already links to the collection)
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.index.tsx

### [P3] "No embedding presets yet" empty-state shown even when /v1/admin/embedding-presets is failing
- Route: /collections (New collection modal)
- Reproduction: Open modal while /v1/admin/embedding-presets is 503/pending
- Expected: Loading or error state for the preset list, not a confident "No embedding presets yet" with a CTA to create one
- Actual: User sees "No embedding presets yet → Go to Models" and is misled into thinking the system has no presets, when really the request just failed
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx:124-139 — branches purely on `presets.length === 0`, ignoring `isLoading` / `error` from `useEmbeddingPresets`

### [P3] No metadata-schema UI in create modal despite API support
- Route: /collections (New collection modal)
- Reproduction: Inspect modal — fields are Name / Description / Vector storage / Embedding preset / Chunk size / Chunk overlap
- Expected: An optional JSON-schema editor (the create payload accepts `metadata_schema` and `tenant_field`, per CreateCollectionRequest)
- Actual: Only basic fields exposed; collections always created with `metadata_schema=null`, `tenant_field=null`
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/create-collection-modal.tsx

### [P3] Embedding API key field missing from create modal
- Route: /collections (New collection modal)
- Reproduction: Inspect modal
- Expected: According to CreateCollectionBody in /Users/yoginth/bigrag/app/src/hooks/use-collections.ts:51, embedding_api_key can be set per-collection. The "presets share API key" model implies it isn't needed here, but the UX should still say that or hide the field deliberately
- Actual: No explicit messaging that API key is inherited from the preset (just a paragraph at the top "Collections share a preset's provider, model, and API key.")
- Note: This may be intentional once presets are the only path, but the help copy is small — easy to miss

### [P4] Brief flash of "No embedding presets yet" empty state on first open
- Route: /collections (New collection modal)
- Reproduction: Hard reload then quickly click "New collection"
- Expected: Modal opens with skeleton/disabled state while presets load
- Actual: For a fraction of a second the "No embedding presets yet" panel flashes before being replaced by the proper "Embedding preset" Select — confusing
- Suspected source: same `presets.length === 0` branch above

## Notes
- Cross-checked the list payload via direct `fetch('/v1/collections?limit=200')`:
  - `arxiv`: openai / text-embedding-3-small / vector_store_provider=turbopuffer / dim=1536 / document_count=7 — matches list table.
  - `test`: openai / text-embedding-3-small / vector_store_provider=qdrant / dim=1536 / document_count=43 — matches list table.
  - Both have `embedding_preset_id` set, but the preset dropdown only shows ONE preset ("Test — openai/text-embedding-3-small"), even though arxiv references a different preset UUID (`d7f6af56-…`). Possibly two presets exist with the same display name — worth verifying on /models.
- Search filter works as a name-prefix filter (`/v1/collections?name=<q>`), but only filters by prefix — typing "rxiv" matches nothing. The placeholder "Search collections" doesn't hint that it's prefix-only.
- Empty state copy ("No collections match" / "Try a different search term.") is good.
- Row navigation goes directly to `/collections/{name}/documents` (Documents tab is the default), not `/collections/{name}` — fine, but URL drift may confuse deep-linking from the list.
- Dev server is severely impacted by parallel tabs — multiple /v1/collections?limit=200 and /v1/admin/embedding-presets requests returned 503 under load. The 503 source could not be located in code (no explicit `status_code=503` raise on these endpoints), so it is likely connection / pool exhaustion bubbling up as 503. Worth investigating uvicorn worker / DB pool sizing for production.
- Modal close (Escape, X icon, Cancel button) all work to dismiss the dialog.
- No keyboard focus-trap issue observed in the modal.
- Sidebar nav highlights "Collections" correctly when on the list page.
- Dark theme rendering looks consistent with the rest of the app.
