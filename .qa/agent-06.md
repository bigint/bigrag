# Agent 6: Collection Settings & Connectors

## Tested
- /collections/arxiv/settings (loaded fully; full traversal done)
- /collections/test/settings (header loaded; form area stuck on spinner during this run)
- /collections/arxiv/connectors (loaded; auto-redirected to google-drive sub-route)
- /collections/arxiv/connectors/google-drive (loaded fully; verified Connect Google button behavior via source code, did NOT click)
- /collections/test/connectors (page never finished loading in this run)
- /collections/test/connectors/google-drive (page never finished loading in this run)
- /connectors (global) — page never finished loading in this run; source code inspection used for the secret-masking + form audit

## Issues

### [P1] Delete-collection confirmation has no destructive-action guard (no type-the-name)
- Route: /collections/arxiv/settings (Danger zone)
- Reproduction:
  1. Open /collections/arxiv/settings, scroll to "Danger zone".
  2. Click "Delete collection".
  3. Observe the alertdialog "Delete arxiv?" with body "This permanently removes the collection, documents, and vectors." and two buttons: Cancel / Delete collection.
- Expected: A high-friction confirmation that requires typing the collection name (or similar guard) before the destructive Delete button enables, since the action is irreversible and removes all docs/vectors.
- Actual: A single click on "Delete collection" inside the dialog will execute the delete immediately; no typed confirmation, no double-confirm, no "I understand" checkbox.
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx (uses ConfirmDialog from /Users/yoginth/bigrag/app/src/components/ui/confirm-dialog.tsx without a typed-confirmation prop)

### [P2] "Remove all documents" (truncate) also has no destructive-action guard
- Route: /collections/arxiv/settings (Danger zone)
- Reproduction:
  1. Open /collections/arxiv/settings, click "Remove all documents".
  2. Observe alertdialog "Remove all documents?" with body "The collection stays, but all documents and vectors are removed." and Cancel / Remove documents buttons.
- Expected: Same as above — destructive bulk-delete should require typed confirmation or at minimum a double-confirm.
- Actual: One click on "Remove documents" executes the truncate.
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx (same ConfirmDialog usage)

### [P2] Settings page for collection "test" never finished loading (form area stuck on spinner)
- Route: /collections/test/settings
- Reproduction:
  1. Navigate to /collections/test/settings after sign-in.
  2. Wait 30s+.
- Expected: The settings form for the "test" collection should render (it loads for "arxiv").
- Actual: Header ("Collection / test / No description set.") and tabs render, but the body region only shows a Spinner — never resolves. No stats-cards row (Documents/Chunks/Tokens/Storage) is shown either, unlike arxiv which renders those.
- Console: none captured
- Network: /v1/auth/me and /v1/auth/setup-status seen as "pending" repeatedly in observation; /v1/collections/test was never observed to complete from the React side during the run. Direct fetch() calls from the same tab succeeded with 200, so the API is reachable — this looks like a stuck React-Query / ky request started during initial app boot that fails to resolve (possibly browser per-host connection-limit exhaustion while many tabs are running concurrently).
- Suspected source: /Users/yoginth/bigrag/app/src/hooks/use-collections.ts useCollection(name) — page renders `<Spinner />` while `collection` is falsy (see /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx lines 63-69). If the initial /v1/collections/{name} request never resolves the user is stuck with no error UI and no retry button.

### [P2] Spinner-only state has no error fallback / retry
- Route: /collections/{name}/settings, /collections/{name}/connectors, /connectors
- Reproduction: Trigger a slow / never-resolving API call (e.g. concurrent load). The page shows only a Spinner indefinitely.
- Expected: After some bounded wait (or on error), show an error banner with a Retry button or a "Failed to load — refresh" affordance.
- Actual: Indefinite spinner. The user has no way to know whether the page is loading, hung, or broken. Same for /collections/{name}/connectors index (which then redirects to google-drive) and for /connectors (which depends on useGoogleConnectorConfig + useGoogleAccount).
- Console: none
- Network: pending /v1/* requests
- Suspected source:
  - /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx (`if (!collection) return Spinner`)
  - /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.connectors.index.tsx (renders Spinner while redirecting)
  - /Users/yoginth/bigrag/app/src/features/connectors/connectors-page.tsx (uses `isPending` from useGoogleConnectorConfig but only branches inside GoogleConnectorPanel — outer shell never surfaces errors)

### [P3] "Embedding key" field — no indication whether one is already saved
- Route: /collections/arxiv/settings
- Reproduction:
  1. Open Settings, locate "Embedding key" card.
  2. Observe the lone input labeled "New API key" with placeholder `sk-...`.
- Expected: A clear indicator of current state ("Currently using shared/inherited key" or "Saved" badge) similar to the global /connectors page which shows a `Saved` placeholder on the OAuth client-secret field when one exists.
- Actual: Only an empty password input with `sk-...` placeholder. The "Update embedding key" button starts disabled but there is no readable status above it.
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx — Embedding key section (no `has_embedding_key` flag is surfaced on the response or rendered).

### [P3] Description field — no dirty/unsaved indicator
- Route: /collections/arxiv/settings (Retrieval defaults card)
- Reproduction:
  1. Type into the Description textarea.
  2. The only action is the standalone "Save defaults" button at the bottom of the card.
- Expected: When the user has unsaved changes, either disable navigation away with a warning, or show a "Unsaved changes" badge / make the Save button visually become primary/highlighted.
- Actual: No visible dirty-state indicator. The user can navigate away (Documents / Search / Settings tab, sidebar link) and silently lose edits.
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/routes/_dashboard.collections.$name.settings.tsx — local useState only, no router blocker / dirty tracking.

### [P3] Per-collection Connectors page only contains Google Drive (no other providers listed)
- Route: /collections/arxiv/connectors/google-drive
- Reproduction:
  1. Open /collections/arxiv/connectors — auto-redirects to /google-drive
  2. Only one tab/pill is shown: "Google Drive". No other providers (S3, Notion, Slack, etc.) listed.
- Expected: If the product positions itself as a connector hub, either show a placeholder/"Coming soon" list of planned providers, or document that Google Drive is the only one. The global /connectors page apparently exposes more (planned) providers via `connectorProviders` and a tabs UI; the per-collection list (`collectionConnectorProviders`) is a strict subset and the UX of "only one tab in a tabs strip" looks unfinished.
- Console: none
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/features/connectors/connector-catalog.ts (`collectionConnectorProviders` exports only google-drive)

### [P4] OAuth "Connect Google" button does not surface where it will redirect
- Route: /collections/arxiv/connectors/google-drive (not-connected state)
- Reproduction:
  1. Observe the "Connect Google" button (rendered when account.data.connected is false).
- Expected: A tooltip / subtext mentioning it will redirect to a Google consent screen, and (ideally) a confirmation step if a previous connection exists.
- Actual: A bare "Connect Google" button. Clicking it issues `GET /v1/connectors/google/oauth/start-url` then assigns `window.location.href = auth_url`, which leaves the app entirely — no user-facing warning that this is a full-page redirect that will leave any in-progress work.
- Console: none (did NOT click per scope)
- Network: none
- Suspected source: /Users/yoginth/bigrag/app/src/features/collections/google-drive-states.tsx ConnectRequired action and /Users/yoginth/bigrag/app/src/features/collections/google-drive-panel.tsx `connect()` (lines 111-122).

## Notes

- Confirmed: the OAuth client-secret input on /connectors uses `type="password"` and shows "Saved" placeholder when a secret already exists in config (`config?.has_client_secret`), and the form value field is left blank — no plaintext secret is rendered. (Verified by reading /Users/yoginth/bigrag/app/src/features/connectors/connectors-page.tsx lines 233-244.) The page itself could not be exercised end-to-end in this run because /connectors never finished its initial spinner — see P2.
- Confirmed: per-collection Embedding key input uses `type="password"` (verified in the DOM dump). No "show/hide" toggle present, but since it's only an entry field (no existing value rendered), that's acceptable.
- Confirmed: /collections/{name}/connectors/google-drive in not-connected state shows "Connect Google Drive" with the logged-in user email and a "Connect Google" button — exactly what was expected. Did not click. Did not exercise Disconnect (would only show when connected).
- Did NOT exercise the "Sync now" / "Resync" controls (those only appear when an account is connected and sources exist; account.connected was false for the testing user during this run).
- ENVIRONMENT NOTE: while testing in parallel with ~10 other agents, the browser tab pool was very volatile (tabs being evicted, login state being kicked, renderer freezing under CDP after 45s). Several screenshots only show an indefinite spinner; the source-code inspection was used to confirm the intended UI for those routes. The "stuck spinner" pages (test/settings, test/connectors/google-drive, /connectors) might or might not reproduce when there is no contention — at minimum the "no error fallback / retry" P2 issue is real and reproducible whenever the initial query is slow.
