# bigRAG — Code Review & Fix Tracker

A consolidated list of issues found across the codebase by parallel review agents
(ingestion + retrieval, routers/auth/middleware, data layer/MCP/bootstrap, Studio
Next.js app, all three SDKs, and docs/website/infra), plus the earlier hand
review.

Each item has:
- a stable ID (`I-001`, etc.) for cross-referencing in PRs/commits
- severity (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW`)
- file path(s) and line numbers
- what's wrong and why it matters
- a concrete fix
- a status checkbox

Where two reports overlapped, items have been merged. A handful of agent
findings I dropped or reframed when the reasoning was wrong (e.g., the
"`hmac.new` doesn't exist" claim — it does; the "`asyncio.run` inside thread
pool" claim — that thread has no running loop).

---

## Table of contents

1. [Status legend](#status-legend)
2. [Top priority — fix first](#top-priority--fix-first)
   - [Critical security holes](#a-critical-security-holes)
   - [Data integrity / multi-process correctness](#b-data-integrity--multi-process-correctness)
   - [Repo / build is currently broken](#c-repo--build-is-currently-broken)
3. [High-priority bugs](#high-priority-bugs)
   - [Auth/scope correctness](#auth--scope-correctness)
   - [Studio app](#studio-app)
   - [Pipeline / retrieval](#pipeline--retrieval)
   - [Backend infra](#backend-infra)
4. [Medium-priority issues](#medium-priority-issues)
5. [SDK drift & inconsistency](#sdk-drift--inconsistency)
6. [Docs / drift cleanup](#docs--drift-cleanup)
7. [Suggested order of attack](#suggested-order-of-attack)
8. [Index by file](#index-by-file)

---

## Status legend

- `[ ]` open
- `[~]` in progress
- `[x]` done
- `[?]` need confirmation / could not verify
- `[-]` won't fix / wontdo (note reason)

Severity badges:
- 🔴 **CRITICAL** — security exploit available today, data corruption, or system
  unable to start.
- 🟠 **HIGH** — real bug that will fire under production load or moderate
  concurrency.
- 🟡 **MEDIUM** — code quality, perf, or drift that's unlikely to bite immediately
  but should be addressed.
- 🟢 **LOW** — nit, doc clean-up, or future-proofing.

---

## Top priority — fix first

### A. Critical security holes

#### `[x]` I-001 🔴 SSRF via `S3IngestRequest.endpoint_url`

**Files:** `api/bigrag/models/s3.py` (lines 9–17), `api/bigrag/routers/documents.py:780`

`endpoint_url` is a free-form `str | None` with **zero validation** in the
Pydantic model. An authenticated API-key holder with the `document:upload` scope
(not even admin) can point it at:

- `http://169.254.169.254/latest/meta-data/` (EC2 IMDS — credential theft)
- internal cluster services (Postgres, Redis, internal HTTP APIs)
- the loopback API itself

The webhook model has a sibling guard (`resolve_and_validate_url`) that already
implements the right check. S3 ingest does not.

**Fix:**
- Apply `resolve_and_validate_url` to `endpoint_url` in `S3IngestRequest`
  (Pydantic `model_validator`).
- Force `https://` only (or http only for explicit localhost).
- Validate at delivery time too (DNS rebinding — see I-004).

---

#### `[x]` I-002 🔴 Idempotency key not scoped to the principal

**File:** `api/bigrag/middleware/idempotency.py:31-33,66-68`

Cache key is `sha256(idem_key | method | path)`. Two different API keys sending
the same `Idempotency-Key: abc123` to the same endpoint **collide**: whichever
fires first caches its 2xx response, and the second caller replays it — getting
back a record (e.g. `document_id`, `collection_id`, `filename`) that belongs to
the first caller's tenant.

**Fix:**
```python
principal = (...)  # API-key hash, or session-cookie hash, or "anon:<ip>"
h = hashlib.sha256(f"{principal}|{idem_key}|{method}|{path}".encode()).hexdigest()
```
The principal is already known to `RateLimitMiddleware._principal`; lift that
helper into a shared module.

---

#### `[x]` I-003 🔴 Per-key rate limits are stored but never applied

**Files:** `api/bigrag/middleware/rate_limit.py` (whole file),
`api/bigrag/middleware/auth.py:108`

`api_key.rate_limits` is loaded onto the principal dict (`middleware/auth.py`)
and surfaced through the API response — but `RateLimitMiddleware._match_rule`
only consults the global `_RULES`. A key configured for
`{"POST:/v1/query": 10}` actually runs at the global 60 RPM. This silently
breaks every per-key throttling decision an operator has made.

**Fix:** In `RateLimitMiddleware.__call__`, after `_principal()` is computed,
fetch the principal's `rate_limits` from the request scope (set there by
`get_current_user`) and prefer those over the global match.

---

#### `[x]` I-004 🔴 Webhook DNS rebinding bypass on SSRF guard

**File:** `api/bigrag/models/webhook.py:26-50`

`resolve_and_validate_url` runs at validation time only (model construction or
PATCH). The actual HTTP delivery happens later, sometimes much later, via a
background task. An attacker who controls a DNS record can:

1. Point `evil.example.com` at a public IP.
2. Submit the webhook URL — validation passes.
3. Flip the DNS to `10.0.0.1` before delivery fires.

Validated URL → internal target.

**Fix:**
- Re-resolve at delivery time inside `_deliver` and apply the same
  private-IP check.
- Better: use an `httpx.AsyncClient(transport=...)` with a custom transport
  that blocks private IPs at the socket level.

---

#### `[x]` I-005 🔴 API key accepted as `?token=` query param leaks via logs

**File:** `api/bigrag/middleware/auth.py:74-76`

The full key `bigrag_sk_…` appears in:
- nginx / Caddy / Cloudflare access logs
- browser history
- HTTP `Referer` headers on outbound links
- exception bodies that include the request URL
- the **Studio MCP page** rendering the URL into the DOM
  (`app/src/app/(dashboard)/mcp/page.tsx:62-63,256`)

The codebase already accepts the key as `Authorization: Bearer …`. The query
param is justified only for SSE/EventSource paths.

**Fix:**
- Restrict query-param auth to a small allowlist of `*/events` and
  `*/progress` SSE endpoints.
- Document the trade-off in `concepts/security.mdx`.
- In Studio, render the token inside an `<input type="password" readonly>` so
  it's not in the rendered text node tree, and clear `credential` state on a
  timer (see I-035).

---

#### `[x]` I-006 🔴 Email enumeration via login response timing

**File:** `api/bigrag/routers/auth.py:144-154`

```python
user = await session.scalar(...)
if user is None or not verify_password(body.password, user.password_hash):
```

Python's `or` short-circuits → no Argon2 verification when the email is
unknown. ~1 ms response vs ~300 ms for a known-but-wrong password. An
attacker can enumerate registered admin emails by timing alone.

**Fix:**
```python
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$..."  # constant valid Argon2 hash

if user is None:
    verify_password(body.password, DUMMY_HASH)  # consume time
    raise HTTPException(401, "Invalid email or password")
```

---

#### `[x]` I-007 🔴 Path traversal in `LocalStorage._safe_path`

**File:** `api/bigrag/services/storage.py:38-40`

```python
if not str(resolved).startswith(str(self._base)):
    raise ValueError(f"Invalid storage key: {key}")
```

Prefix check, not directory check. With `self._base = /data/uploads`, the path
`/data/uploads_evil/file` passes (`/data/uploads_evil` starts with
`/data/uploads`).

**Fix:**
```python
if resolved != self._base and self._base not in resolved.parents:
    raise ValueError(...)
```
or `os.path.commonpath([resolved, self._base]) == str(self._base)`.

---

#### `[x]` I-008 🔴 Milvus filter-expression injection in `text_search`

**File:** `api/bigrag/services/vector_store.py:338-339`

```python
escaped = term.replace("\\", "\\\\").replace('"', '\\"').replace("%", "\\%")
term_filters.append(f'text like "%{escaped}%"')
```

Single quotes (`'`) are not escaped. A query term containing `'` produces a
malformed Milvus expression and can be turned into expression injection that
short-circuits filters or accesses other partitions. The broader escape used by
`retrieval._build_filter_expr` is correct; reuse it.

**Fix:** Add `'` to the escape set, or pass terms through Milvus's parameterized
expression API if/when available.

---

#### `[x]` I-009 🔴 `Content-Disposition` header injection via `doc.filename`

**File:** `api/bigrag/routers/documents.py:555-560`

```python
filename = doc.filename.replace('"', '\\"')
return Response(..., headers={"Content-Disposition": f'attachment; filename="{filename}"'})
```

Only `"` is escaped. A filename with `\r\n` allows HTTP response splitting.

**Fix:**
```python
import re
safe = re.sub(r'[^\x20-\x7e]', '_', doc.filename).replace('"', '\\"')
```
Or use RFC 5987 encoding: `filename*=UTF-8''<percent-encoded>`.

---

#### `[x]` I-010 🔴 Open redirect via Studio proxy

**File:** `app/src/app/api/bigrag/[...path]/route.ts:40,68`

```ts
upstream = await fetch(target, { ..., redirect: "manual" });
return new Response(body, { status: upstream.status, headers: responseHeaders });
```

`redirect: "manual"` captures the upstream `Location` header verbatim and
forwards it to the browser. If the backend ever emits a redirect (intentional
or accidental), the browser follows it without any host validation.

**Fix:** validate `Location` starts with `BIGRAG_URL` before forwarding, or
switch to `redirect: "follow"` and strip `Location` from the response headers.

---

#### `[x]` I-011 🔴 No CSRF protection on the Studio proxy

**Files:** `app/src/app/api/bigrag/[...path]/route.ts`, `app/src/lib/api.ts:5`

ky sets `credentials: "include"`. The proxy exports `POST/PUT/PATCH/DELETE`
without origin/referrer checks, no double-submit token, no SameSite enforcement
beyond whatever the cookie default carries. A malicious page on a different
origin can trigger a cross-origin form POST to e.g.
`/api/bigrag/v1/admin/api-keys`; the browser sends the session cookie and the
proxy faithfully forwards.

**Fix:**
- Reject mutating methods unless `Origin` matches `Host` (or the configured
  Studio origin).
- Add a synchronizer-token / double-submit cookie pair if forms are ever
  submitted via plain `<form>`.

---

#### `[x]` I-012 🔴 OpenAI key sent direct from browser, no CSP

**Files:** `app/src/lib/openai-stream.ts:28`, `app/next.config.ts`

`fetch("https://api.openai.com/...", { Authorization: Bearer sk-... })` runs
client-side. The Next config sets `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy` — but **no CSP at all**. Any future XSS, malicious browser
extension, or CDN-injected script can read the key from React state /
TanStack Query cache and exfiltrate it.

Also: the key is also persisted to `user_preferences` server-side as plain
JSONB (already on the list as I-046).

**Fix:**
- Add a CSP in `next.config.ts`:
  ```
  default-src 'self';
  script-src 'self';
  connect-src 'self' https://api.openai.com;
  img-src 'self' data:;
  style-src 'self' 'unsafe-inline';
  ```
- Longer term: proxy the OpenAI stream through a Next.js server route so the
  key never touches the browser.

---

### B. Data integrity / multi-process correctness

#### `[x]` I-013 🔴 Stuck-job recovery races with running workers

**File:** `api/bigrag/services/queue.py:90-99`

`_recover_stuck_jobs` runs unconditionally on startup and moves every entry in
`bigrag:ingestion:processing` back into `bigrag:ingestion:queue`. With multiple
uvicorn workers (or a rolling deploy), a job actively running in process A is
moved back and re-claimed by process B → duplicate Milvus inserts, double
`document_count` increment, possibly conflicting status writes.

**Fix:** Use heartbeat-keyed leases. A worker takes a job by writing a
`processing:<job_id>` key with TTL `now + 2 × poll_interval`. Recovery moves
back only jobs whose heartbeat key has expired.

---

#### `[x]` I-014 🔴 Multi-process SSE never receives "complete"

**File:** `api/bigrag/services/event_bus.py:147-149`

```python
def complete(self, document_id: str) -> None:
    for q in self._subs.get(document_id, []):
        q.put_nowait(None)
```

This writes the `None` sentinel into in-process queues only — does not publish
to Redis. With ≥2 uvicorn workers, an SSE listener on a different worker hangs
until the 600 s timeout.

**Fix:**
- Publish a `{"_complete": true, "document_id": ...}` marker over Redis pub/sub
  in `complete()`.
- In `_listen`, translate that marker into a local `None` write.

---

#### `[x]` I-015 🔴 `Collection.document_count` drift on reprocess + on zero-chunk "ready"

**Files:** `api/bigrag/services/queue.py:499-515`,
`api/bigrag/routers/documents.py:reprocess_document`

The worker increments `document_count` whenever a job ends in `status=ready`.
- `reprocess_document` flips status from `ready → pending → ready` without
  decrementing → counter inflates by 1 per reprocess.
- If every embedding batch hits its retry cap and `total_inserted == 0`, the
  doc is still marked `ready` and `document_count` still increments → silent
  partial failure with 0 chunks but a bumped counter.

**Fix:**
- Gate the increment on `total_inserted > 0` AND a real `pending → ready`
  transition (compare prior status before update).
- Ideally drop the denormalized counter entirely and `SELECT COUNT(*) FROM
  documents WHERE collection_id = $1 AND status = 'ready'` (the
  `idx_documents_collection_id` index makes this cheap).
- Mark partial-success docs with `error_message="Partial: N/M chunks
  embedded"` so operators can find them.

---

#### `[x]` I-016 🔴 S3 ingest counters get lost-update across coroutines

**File:** `api/bigrag/services/s3_ingest.py:217-218,303,331,248-249,268-269`

`_download_and_ingest` is dispatched via `asyncio.gather`. Each coroutine reads
`ingested` / `skipped` (via `nonlocal`) before its `await` and writes back
after. Two concurrent coroutines reading the same value → lost increment.

**Fix:** Wrap counter mutations in an `asyncio.Lock`, or accumulate per-task
locally and reduce after `gather` completes.

---

#### `[x]` I-017 🔴 Blocking pymilvus calls on the event loop

**Files:** `api/bigrag/services/vector_store.py:290,314`,
`api/bigrag/routers/health.py:81-87`

- `vector_store.get_chunks` and `delete_by_document` call
  `self.client.has_collection(col)` directly (synchronous gRPC).
- `health._check_milvus` calls `vs.client.list_collections()` directly.

Both stall the event loop for the duration of the network round-trip.

**Fix:** Wrap with `await self._run_with_retry(self.client.has_collection, col)`
in vector_store, and `await asyncio.to_thread(vs.client.list_collections)` in
the health check.

---

#### `[x]` I-018 🔴 Semantic cache is checked **after** full retrieval

**File:** `api/bigrag/routers/query.py:60-85`

`retrieve(...)` always runs to completion (embed → search → optional rerank →
optional MMR), and only then does the route consult the semantic cache. The
"cache hit replay" path early-returns at line 85 — but by then we've paid the
embedding + search + rerank latency. The cache saves zero compute on hits.

**Fix:** Embed the query first, look up the cache against that embedding, and
short-circuit before calling `retrieve()` on a hit.

---

#### `[x]` I-019 🔴 Python SDK `_request_form` has no retry loop

**File:** `sdks/python/src/bigrag/_core.py:136-158`

`_request_form` calls `self._client.post(...)` directly with no retry, unlike
`_request`. Document upload returns 503 when the ingestion queue is full
(`routers/documents.py:188-192`); the SDK raises immediately rather than
retrying.

**Fix:** Mirror the retry loop in `_request` (same backoff, same retryable
status codes). Better: extract a shared `_execute_with_retry` helper.

---

### C. Repo / build is currently broken

#### `[x]` I-020 🔴 Dockerfile never copies `alembic/` or `alembic.ini`

**File:** `api/Dockerfile:17-19`

`bootstrap.run_migrations` resolves the Alembic config relative to the
installed package (`/opt/venv/lib/python3.12/site-packages/bigrag/db/...`).
The migration files only exist at `/Users/yoginth/bigrag/api/alembic/`. The
container starts → `FileNotFoundError`.

**Fix:** Either include the migration directory as package data in
`pyproject.toml` (`[tool.hatch.build].packages` or `include`), or `COPY
alembic/ alembic/` and `COPY alembic.ini .` in the Dockerfile, and resolve the
config via an env var rather than `__file__`-relative path arithmetic.

**This makes the published `yoginth/bigrag:latest` image non-functional out of
the box.**

---

#### `[x]` I-021 🔴 CI uses `actions/checkout@v6` (does not exist)

**File:** `.github/workflows/ci.yml:13,35,43,64,84`

Latest stable is `@v4`. `astral-sh/setup-uv@v6` is also wrong (current is
`@v5`). Every CI run fails on checkout.

**Fix:** `actions/checkout@v4`, `astral-sh/setup-uv@v5`. Verify
`biomejs/setup-biome@v2` (probably valid).

---

#### `[x]` I-022 🔴 Initial Alembic migration uses `Base.metadata.create_all`

**File:** `api/alembic/versions/0001_initial_schema.py:29`

Bypasses Alembic's DDL tracking. Future `alembic revision --autogenerate` runs
will diff a populated DB against the same `Base.metadata`, find nothing, and
emit empty migrations forever. Schema drift becomes invisible.

**Fix:** Replace with the explicit `op.create_table(...)` / `op.create_index`
baseline that autogenerate would have produced from a fresh DB. One-time
conversion: `alembic revision --autogenerate -m "baseline"` against an empty
database, copy the body into `0001`.

---

#### `[x]` I-023 🔴 Cleanup task isn't awaited; exception swallowed

**File:** `api/bigrag/main.py:89,103`

```python
cleanup_task = asyncio.create_task(cleanup_old_data())
...
cleanup_task.cancel()  # not awaited
```

If `cleanup_old_data` holds a DB connection or raises, the exception is
silently dropped (no done-callback), and the task is cancelled but never
joined.

**Fix:** Use `safe_create_task` (already in `utils.py`) and `await` after cancel:
```python
cleanup_task = safe_create_task(cleanup_old_data(), name="cleanup")
...
cleanup_task.cancel()
try:
    await cleanup_task
except asyncio.CancelledError:
    pass
```

---

## High-priority bugs

### Auth & scope correctness

#### `[x]` I-024 🟠 Reembed and truncate are unscoped

**File:** `api/bigrag/services/scopes.py` (no entry for these endpoints)

`POST /v1/collections/{name}/reembed` requeues every document for embedding —
significant compute and provider-API cost — and `POST .../truncate` deletes all
documents and vectors. Both have no `_ENDPOINT_SCOPES` entry, so any
authenticated key (including a `query:read`-only key) passes.

**Fix:** Add:
```python
("POST", "/v1/collections/{name}/reembed", "collection:write"),
("POST", "/v1/collections/{name}/truncate", "collection:delete"),
```

---

#### `[x]` I-025 🟠 `GET /v1/documents/{id}/chunks` is unscoped

**File:** `api/bigrag/services/scopes.py:31`

The rule `("GET", "/v1/documents/", "document:read")` matches `/v1/documents/`
but the path-matcher's prefix logic only catches `GET /v1/documents/{id}` — the
chunks variant slips through. Add an explicit rule.

**Fix:**
```python
("GET", "/v1/documents/{id}/chunks", "document:read"),
("GET", "/v1/documents/{id}", "document:read"),
```

---

#### `[x]` I-026 🟠 `enforce_collection_scope` allows pinned keys to mutate their pinned collection

**File:** `api/bigrag/services/collection_scope.py:46-63`

`_FORBIDDEN_FOR_SCOPED` blocks `("GET", "/v1/collections")` and
`("POST", "/v1/collections")` but not `PUT`/`DELETE` on `/v1/collections/{name}`.
A read-only or upload-only pinned key can therefore `PUT` (mutate config) or
`DELETE` its own collection.

**Fix:** Either add method-aware rules to `_FORBIDDEN_FOR_SCOPED`, or reject all
`PUT`/`DELETE` on `/v1/collections/{name}` for pinned keys.

---

#### `[x]` I-027 🟠 No brute-force throttle on login/setup

**File:** `api/bigrag/middleware/rate_limit.py:30-36`

Catch-all is 120 RPM/IP. `/v1/auth/login` and `/v1/auth/setup` should have
much tighter limits (e.g. 5/min and 3/min per IP).

**Fix:** Add explicit rules:
```python
("POST", "/v1/auth/login", 5),
("POST", "/v1/auth/setup", 3),
```

---

#### `[x]` I-028 🟠 Webhook mutations are unaudited

**File:** `api/bigrag/routers/webhooks.py` (entire file)

None of `create_webhook`, `update_webhook`, `delete_webhook`, `test_webhook`,
or `replay_delivery` call `audit.record(...)`. Webhooks are an exfiltration
vector; their lifecycle is the most-audited surface in any sane system.

**Fix:** Add `audit.record(...)` calls matching `admin_api_keys.py`'s pattern.
Categories: `webhook.create`, `webhook.update`, `webhook.delete`,
`webhook.test`, `webhook.replay`.

---

#### `[x]` I-029 🟠 `EncryptedString` plaintext fallback flows into Redis cache

**Files:** `api/bigrag/services/crypto.py:88-101`,
`api/bigrag/services/collection_cache.py:_serialize`

If a row contains a plaintext value (legacy data, restored backup, partially
migrated state), `process_result_value` returns it. The collection cache then
stores `embedding_api_key` into Redis — unencrypted — for `collection_cache_ttl`
seconds (30 s by default).

**Fix:** Either return `None` and force a re-upload of the key, or never cache
`embedding_api_key` server-side (read it on demand, or only cache `has_api_key:
bool`).

---

#### `[x]` I-030 🟠 `/health/ready` leaks provider error details, unauthenticated

**File:** `api/bigrag/routers/health.py:53-60`

`error_msg = str(exc)[:200]` from an OpenAI/Cohere rejection can include
fragments of base URLs, account hints, and worded mentions that a key is
invalid. `/health/ready` is anonymous and the result is cached in Redis for
60 s.

**Fix:** Map exceptions to categories (`auth_failed`, `unreachable`,
`rate_limited`, `unknown`) and return only the category. Optionally gate the
embedding sub-check behind an auth header.

---

#### `[x]` I-031 🟠 Last-admin TOCTOU race

**File:** `api/bigrag/routers/admin_users.py:138-150`

Count-then-delete in two statements. Two concurrent admin deletes can both
pass the "remaining_admins > 0" check. System ends with zero admins.

**Fix:** Single atomic SQL:
```sql
DELETE FROM users
WHERE id = :id
  AND (SELECT count(*) FROM users WHERE role='admin') > 1
```
Then check `rowcount` to decide whether to 200 or 400.

---

#### `[x]` I-032 🟠 `/v1/auth/logout-all` accepts API keys

**File:** `api/bigrag/routers/auth.py:165`

Documented as session-only but uses `Depends(get_current_user)`. Any minted
key can log its owning user out of all sessions.

**Fix:** Switch to `Depends(require_session)`.

---

#### `[x]` I-033 🟠 `POST /v1/auth/setup` returns 403, docs say 409

**File:** `api/bigrag/routers/auth.py:106` vs
`website/content/docs/api-reference/authentication.mdx:167`

```python
raise HTTPException(status_code=403, detail="Setup has already been completed")
```

**Fix:** Change to 409. (Or update the docs everywhere — but 409 is the
correct REST semantic for "resource already exists".)

---

### Studio app

#### `[x]` I-034 🟠 Studio proxy forwards backend `Set-Cookie` verbatim

**File:** `app/src/app/api/bigrag/[...path]/route.ts:HOP_HEADERS`

The hop-header denylist doesn't strip `set-cookie`. The backend can plant
cookies at the Next.js origin with arbitrary attributes (no `Secure`, no
`SameSite`).

**Fix:** Add `set-cookie` to `HOP_HEADERS`. Authenticate to upstream via the
`Authorization` header or a dedicated cookie that Next.js mints itself.

---

#### `[ ]` I-035 🟠 MCP page renders the full token in the DOM

**File:** `app/src/app/(dashboard)/mcp/page.tsx:62-63,256`

The credential dialog renders the URL with the embedded plaintext API key
inside a `<pre><code>` block. React DevTools, malicious extensions, and the
React fiber tree all see it. The modal stays mounted until the user clicks
"I've saved the URL" — could be hours.

**Fix:**
- Show the key inside `<input type="password" readonly>` so it's not in the
  DOM text.
- Auto-clear `credential` state after 5 minutes.
- Consider a `/mcp/connect?session=<short-lived-code>` exchange so the
  long-lived key never appears in a URL.

---

#### `[ ]` I-036 🟠 Shell snippet on the MCP page isn't shell-quoted

**File:** `app/src/app/(dashboard)/mcp/page.tsx:82-85`

```ts
`BIGRAG_URL=${origin} BIGRAG_API_KEY=${plaintext} bigrag-mcp`
```

If origin or key contains a shell metacharacter, the snippet either breaks or
injects shell commands into the user's shell on copy-paste. Today's keys
don't, but the URL is operator-controlled.

**Fix:**
```ts
const sq = (s: string) => `'${s.replace(/'/g, "'\\''")}'`;
return `BIGRAG_URL=${sq(origin)} BIGRAG_API_KEY=${sq(plaintext)} bigrag-mcp`;
```

---

#### `[ ]` I-037 🟠 `useSession` swallows non-401 errors as "logged out"

**File:** `app/src/hooks/use-auth.ts:30-37`

Any HTTP error → `null` session → dashboard redirects to `/login`. Transient
500s during a deploy log everyone out.

**Fix:**
```ts
const status = (err as { status?: number }).status;
if (status === 401) return null;
throw err;
```

---

#### `[ ]` I-038 🟠 Logout invalidates *all* queries → 401 storm before redirect

**File:** `app/src/hooks/use-auth.ts:59-64,71-76`

`qc.invalidateQueries()` triggers a refetch on every active observer, all of
which 401 (cookie is gone). The `beforeError` hook fires error toasts during
the redirect.

**Fix:** Use `qc.clear()` or `qc.removeQueries()` — removes data without
refetching.

---

#### `[ ]` I-039 🟠 Setup-status redirect can race a valid session

**File:** `app/src/app/(dashboard)/layout.tsx:18-27`

`useSetupStatus` and `useSession` race. If `setupStatus.needs_setup` resolves
first with `true` (transient backend hiccup), the layout redirects to `/setup`
even though the session is valid.

**Fix:** Only act on `setupStatus.needs_setup` after `useSession` has resolved
to `null`. The decision tree should be: session ok → continue; session null →
check setup → redirect to `/setup` or `/login`.

---

#### `[ ]` I-040 🟠 Webhook URL form accepts `javascript:` scheme

**File:** `app/src/app/(dashboard)/webhooks/components/webhook-form.tsx:71-73`

`new URL("javascript:alert(1)")` is valid. The server already rejects this,
but the UI shouldn't round-trip it.

**Fix:**
```ts
const parsed = new URL(url);
if (!['http:', 'https:'].includes(parsed.protocol)) {
  return setFormError("Webhook URL must use http or https");
}
```

---

#### `[ ]` I-041 🟠 `useUpdateApiKey` has no error toast

**File:** `app/src/hooks/use-api-keys.ts:26-39`

Toggling the active switch on the API-keys page silently fails on backend
error. The Switch flips visually (no optimistic update means it reverts only
on the next refetch), no toast, no feedback.

**Fix:** Add:
```ts
onError: (err) => toast.error(err instanceof Error ? err.message : "Failed to update key"),
```

---

#### `[ ]` I-042 🟠 ky retries non-idempotent POSTs

**File:** `app/src/lib/api.ts:3-7`

`retry: { limit: 1 }` retries on network failure for any method by default. A
timed-out create-collection / create-key can be retried, producing duplicates.

**Fix:**
```ts
retry: { limit: 1, methods: ['get', 'head'] },
```

---

#### `[ ]` I-043 🟠 `NEXT_PUBLIC_BIGRAG_URL` rendered into login error page

**File:** `app/src/app/(auth)/login/page.tsx:43-47`

When the backend is unreachable, the page shows the internal hostname (e.g.
`http://bigrag-api.internal:6100`). Anyone who can hit the login screen during
a backend hiccup learns the internal URL.

**Fix:** Show the URL only when `process.env.NODE_ENV === "development"`. In
prod, show a generic "bigRAG API is not reachable".

---

#### `[x]` I-044 🟠 Studio proxy forwards arbitrary client headers upstream

**File:** `app/src/app/api/bigrag/[...path]/route.ts:32-36`

Every header that's not in the narrow hop-header list is forwarded to
`BIGRAG_URL`. A user supplying `X-Forwarded-Host`, `X-Real-IP`, or any other
header has those forwarded verbatim into an internal request.

**Fix:** Replace the denylist with an allowlist: only forward `content-type`,
`accept`, `accept-encoding`, `authorization`, `cookie`, `idempotency-key`, and
any other known-needed headers.

---

#### `[x]` I-045 🟠 Proxy buffers full upload body in memory

**File:** `app/src/app/api/bigrag/[...path]/route.ts:43`

```ts
body: hasBody ? await req.arrayBuffer() : undefined,
```

`BIGRAG_MAX_UPLOAD_SIZE_MB=1024` → up to 1 GB held in the Next process per
upload.

**Fix:**
```ts
body: hasBody ? req.body : undefined,
duplex: hasBody ? "half" : undefined,
```

---

### Pipeline / retrieval

#### `[x]` I-046 🟠 OpenAI key stored unencrypted in `user_preferences`

**Files:** `app/src/app/(dashboard)/playground/components/chat-input.tsx:160`,
`api/bigrag/db/models.py:323-330`

Studio playground saves `playground.openai_key` into `UserPreference.data`
(plain JSONB). Any DB dump leaks every Studio user's OpenAI key.

**Fix:** Either
- Wrap the `data` column in `EncryptedString` (re-encrypts everything inside
  on rotation, but the key set is tiny) — simplest, but every preference
  touch becomes a Fernet round-trip.
- Or store sensitive keys in a separate, encrypted side-table.
- Or keep the key client-only (localStorage) and accept the device-pinning
  cost.

---

#### `[ ]` I-047 🟠 MMR has no effect (silent no-op)

**Files:** `api/bigrag/services/retrieval.py:170-202`,
`api/bigrag/services/vector_store.py:241-248`

`vector_store.search` does not request `embedding` in `output_fields`, so all
MMR candidates have `embedding=None`. `mmr_rerank` then falls back to
`lambda * relevance` — i.e. pure relevance, no diversity. The `diversity`
parameter is silently ignored.

**Fix:** When the caller passes `diversity != None`, request `embedding` in
`output_fields` (it costs more bytes over the wire — gate it on the request
flag). Then MMR actually picks novel items.

---

#### `[ ]` I-048 🟠 Webhook dispatcher reads collection from wrong field; empty UUID raises

**File:** `api/bigrag/services/webhook.py:202-207`

```python
collection = event.detail.get("collection")
if not collection:
    collection = await self._get_collection_for_document(event.document_id)
```

`event.detail` never has a `"collection"` key — `IngestionEvent` exposes it as
`collection_name`. So every event hits the DB lookup. Worse, search/retrieval
events use empty `document_id`, and `uuid.UUID("")` raises in
`_get_collection_for_document`.

**Fix:**
```python
collection = event.collection_name
if not collection and event.document_id:
    collection = await self._get_collection_for_document(event.document_id)
if not collection:
    return  # nothing we can match
```

---

#### `[ ]` I-049 🟠 Webhook circuit breaker is per-process; never resets without success

**File:** `api/bigrag/services/webhook.py:76-107`

`CircuitBreaker._state` is a Python dict on a per-process dispatcher. Multi
worker = uncoordinated state. Worse: a permanently-broken endpoint
- accumulates failures in process A
- after `cooldown_seconds` enters half-open
- next attempt fails
- ...but `record_failure` increments without resetting failures-counter, so
  the breaker re-opens immediately. It will allow one delivery attempt every
  `cooldown_seconds` forever.

**Fix:** Move state to Redis with a TTL key per webhook. On success, `DEL` the
key. On failure, `INCR` with `EX cooldown_seconds`. Standard token-bucket
breaker.

---

#### `[ ]` I-050 🟠 `flush_collection` is non-atomic

**File:** `api/bigrag/services/queue.py:115-135`

`lrange` snapshot + per-item `lrem`. Workers can pop concurrently; new uploads
during the flush land in the queue but aren't in the snapshot.

**Fix:** Lua script:
```lua
local items = redis.call('LRANGE', KEYS[1], 0, -1)
local kept = {}
for _, raw in ipairs(items) do
  local job = cjson.decode(raw)
  if job['collection_name'] ~= ARGV[1] then
    table.insert(kept, raw)
  end
end
redis.call('DEL', KEYS[1])
if #kept > 0 then redis.call('RPUSH', KEYS[1], unpack(kept)) end
return #items - #kept
```

---

#### `[ ]` I-051 🟠 Queue depth check is TOCTOU

**File:** `api/bigrag/services/queue.py:101-107`

`llen` then `lpush` — not atomic. Concurrent enqueues can blow past
`queue_max_depth` by up to `concurrent_enqueuers - 1`.

**Fix:** Lua script that does the check + push atomically.

---

#### `[ ]` I-052 🟠 `_docling_converter` lazy init isn't thread-safe

**File:** `api/bigrag/services/conversion.py:7-46`

Module-level singleton with no lock. Two `asyncio.to_thread(_write_and_convert)`
calls during cold start race the init; HF model load happens twice. The
second-completed converter wins; any state in the first is silently dropped.

**Fix:**
```python
_docling_lock = threading.Lock()

def _get_docling_converter():
    global _docling_converter
    if _docling_converter is not None:
        return _docling_converter
    with _docling_lock:
        if _docling_converter is None:
            _docling_converter = ...
    return _docling_converter
```

---

#### `[ ]` I-053 🟠 Embedding-model `_models` cache is unbounded

**File:** `api/bigrag/services/embedding.py:249-279`

Cache keyed on `(provider, model, hash(api_key)[:8], hash(base_url)[:6])`.
Rotating API keys → new entries → leaked `httpx.AsyncClient` connection pools.

**Fix:** `cachetools.LRUCache(32)` or similar. Add an `__exit__`/`close` path
on eviction.

---

#### `[ ]` I-054 🟠 Embedding cache key vs truncation

**Files:** `api/bigrag/services/queue.py:_embed_with_cache`,
`api/bigrag/services/embedding.py:163,216`

Cache key = `sha256(text)`. Embedding is for `truncate_to_tokens(text)`. Two
texts that differ only past the token limit have different keys but produce
identical vectors → wasted dedup. (The stored vector is correct; the dedup
guarantee is broken.)

**Fix:** Hash the post-truncation text, or include the truncation length in
the key. Easiest: have `embed()` return both the truncated input and the
vector, and key the cache on the truncated input.

---

#### `[ ]` I-055 🟠 Semantic-cache cosine on the event loop

**File:** `api/bigrag/services/semantic_cache.py:77-97`

Up to 200 × 1536 multiplications per query, synchronous. At 50 req/s this
visibly degrades event-loop latency.

**Fix:** Vectorize via numpy and run inside `asyncio.to_thread`:
```python
import numpy as np
mat = np.array([entry["vec"] for entry in raw_entries])  # (N, D)
q = np.array(query_vec)
scores = (mat @ q) / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q))
```

---

#### `[ ]` I-056 🟠 S3 object body fully buffered, twice

**File:** `api/bigrag/services/s3_ingest.py:261-263`

```python
content = await resp["Body"].read()
...
await storage.put(storage_key, content)
```

Whole object held in RAM, then again at the storage put. The 2 GB metadata
size guard doesn't catch gzipped bodies that decompress past it.

**Fix:** Stream to a temp file (`tempfile.NamedTemporaryFile`) and stream into
storage. Add a streaming `LocalStorage.put_stream(key, stream)` /
`S3Storage.put_stream` API.

---

### Backend infra

#### `[ ]` I-057 🟠 `pool_min` is silently ignored; pool always at `pool_max`

**File:** `api/bigrag/db/engine.py:35`

```python
_engine = create_async_engine(
    url, pool_size=pool_max, max_overflow=0, ...
)
```

Pool is created at the max size and never shrinks; `pool_min` does nothing.

**Fix:**
```python
_engine = create_async_engine(
    url,
    pool_size=pool_min,
    max_overflow=pool_max - pool_min,
    ...
)
```

---

#### `[ ]` I-058 🟠 `cors_origins=[]` silently breaks all browser clients

**Files:** `api/bigrag/config.py:22`, `api/bigrag/main.py:129-134`

Empty list → CORSMiddleware blocks every cross-origin request. No error
surfaced.

**Fix:** Add a startup-guard warning when `env != "dev"` and `cors_origins` is
empty. Set a sensible dev default like `["http://localhost:3000",
"http://localhost:5173", "http://localhost:3100"]`.

---

#### `[ ]` I-059 🟠 `session_cookie_secure=False` only checked when `env == "prod"` exactly

**Files:** `api/bigrag/config.py:36`, `api/bigrag/startup_guard.py:27`

Operators using `env=production`, `staging`, etc. silently get insecure
cookies.

**Fix:** Either
- Type `env` as `Literal["dev", "prod"]` and reject other values at parse
  time, or
- Invert the check: `if s.env != "dev": run_secure_cookie_check(s)`.

---

#### `[ ]` I-060 🟠 `TSupd.onupdate=sa.text("now()")`

**File:** `api/bigrag/db/base.py:28`

`mapped_column`'s `onupdate` expects a callable or an SQLA `func`, not a
`TextClause`. Today this can produce stale `updated_at` columns on UPDATEs
that go through the ORM (depending on SQLAlchemy version).

**Fix:**
```python
TSupd = Annotated[
    datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    ),
]
```

---

#### `[ ]` I-061 🟠 `QueryLog` has no FK to `collections`

**File:** `api/bigrag/db/models.py:232-249`

`collection_name` is plain text; deleting a collection leaves orphaned rows.
No retention/TTL index. Table grows unboundedly.

**Fix:**
- Add `collection_id UUID REFERENCES collections(id) ON DELETE CASCADE`.
- Index `created_at` and run a periodic delete (the cleanup task already
  exists).

---

#### `[ ]` I-062 🟠 Token leakage in URLs (MCP HTTP)

**Files:** `api/bigrag/services/mcp_http.py:49`, `api/bigrag/logging.py:141`

`_TokenExtractMiddleware` accepts `?token=`. The `RequestLoggingMiddleware`
logs only the path (not the query), but proxies / FastAPI default error
handlers / browsers' Referer policy will leak the full URL anyway.

**Fix:** Same as I-005 — restrict query-param auth, prefer header-based
delivery.

---

#### `[ ]` I-063 🟠 MCP tool inputs not path-sanitized

**Files:** `api/bigrag/mcp_server.py` (multiple places),
`api/bigrag/services/mcp_http.py` (multiple)

`collection: str` and `document_id: str` are interpolated into URL paths
without validation. A prompt-injected LLM could pass
`collection="../../admin"` or one with embedded `/`. In `mcp_http.py` this
hits the loopback ASGI transport which has no network firewalling.

**Fix:** `Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')` on collection,
`Field(pattern=r'^[0-9a-fA-F-]{36}$')` on UUID parameters.

---

## Medium-priority issues

#### `[ ]` I-064 🟡 `_models` / global semaphore is shared across providers

**File:** `api/bigrag/services/embedding.py:11-34`

One global `asyncio.Semaphore` (size 8) shared between OpenAI and Cohere. A
slow Cohere call eats OpenAI's parallelism budget and vice versa.

**Fix:** Per-`(provider, base_url)` semaphore. Tied to the cache key set.

---

#### `[ ]` I-065 🟡 Moderation runs on raw binary upload bytes

**File:** `api/bigrag/routers/documents.py:100-111`

```python
text_preview = content[:50_000].decode("utf-8", errors="ignore")
```

For a PDF/DOCX/PPTX, this is mostly garbage shipped to OpenAI's moderation
endpoint. Wastes API calls; can produce false positives on binary noise.

**Fix:** Skip moderation for binary types. Run it after Docling extracts text
in the worker (move from upload-time to post-extraction; reject the doc and
delete from storage if flagged).

---

#### `[ ]` I-066 🟡 Moderation only checks first 10 KB of text

**File:** `api/bigrag/services/moderation.py:33`

```python
client.moderations.create(input=text[:10_000])
```

Trivially bypassable: prepend 10 KB of innocuous text before the prohibited
content.

**Fix:** Sliding window or reject any flagged window. Document the trade-off.

---

#### `[ ]` I-067 🟡 `last_used_at` writes commit on every API call

**File:** `api/bigrag/middleware/auth.py:97-98`

Every authenticated request → `UPDATE api_keys SET last_used_at` + `commit()`.
High-QPS keys hammer the row.

**Fix:** Batch in Redis with a periodic flush, or only write when the existing
value is older than ~60 s:
```python
if api_key.last_used_at is None or (now - api_key.last_used_at).total_seconds() > 60:
    await session.execute(...)
    await session.commit()
```

---

#### `[ ]` I-068 🟡 `request.client` ignores X-Forwarded-For

**Files:** `api/bigrag/services/audit.py:71`,
`api/bigrag/middleware/rate_limit.py:67-78`

Behind any reverse proxy, all audit log entries and rate-limit principals show
the proxy's IP. Documented architecture explicitly assumes a reverse proxy.

**Fix:** Add `BIGRAG_TRUSTED_PROXIES` setting (CIDR list); when the immediate
client is in the list, use the rightmost untrusted IP from `X-Forwarded-For`.

---

#### `[ ]` I-069 🟡 Zip-bomb detection trusts central-directory `file_size`

**File:** `api/bigrag/services/file_validation.py:79-85`

`file_size` in the central directory is attacker-controlled. Cheap defense as
written, but easily fooled. Combine with a streaming decompress that aborts
past `MAX_DECOMPRESSED_BYTES` for collections that accept untrusted uploads.

---

#### `[ ]` I-070 🟡 No master-key rotation path

**File:** `api/bigrag/services/crypto.py:36-49`,
`website/content/docs/deployment/encryption.mdx`

Docs describe a manual SQL migration. Even a `BIGRAG_MASTER_KEY_PREVIOUS`
dual-read mode would beat that.

**Fix:** Add a `crypto.decrypt` that tries `_fernet` first, then a list of
"previous" Fernet instances. Add a `bigrag crypto rotate` CLI that re-encrypts
every encrypted column under the new key.

---

#### `[ ]` I-071 🟡 `batch_progress_sse` subscribes to `*` (every event in the system)

**Files:** `api/bigrag/routers/documents.py:881-958`

Every SSE connection receives every event from every collection, then filters
client-side by `document_id in progress_map`. O(events × connections) per
second. With high ingest load this is real.

**Fix:** Subscribe per-document_id and `asyncio.gather` the queues. Add a
collection-scoped channel for the multi-doc case.

---

#### `[ ]` I-072 🟡 SSE batch progress doesn't validate doc IDs vs the collection

**File:** `api/bigrag/routers/documents.py:881-958`

A collection-pinned key can pass arbitrary UUIDs in `?ids=`. The handler
subscribes to `*` and emits matching events without checking that those doc
IDs belong to the pinned collection. Information leak: progress signals from
other collections.

**Fix:** Validate every supplied `document_id` belongs to `collection_name`
before opening the stream.

---

#### `[ ]` I-073 🟡 `prune_oldest` is a full-table sort

**File:** `api/bigrag/services/embedding_cache.py:136-158`

`SELECT ... ORDER BY last_hit_at OFFSET keep` on a 500K-row table is a full
sort. At 1M+ rows this holds a long-lived transaction and lock.

**Fix:**
```python
DELETE FROM embedding_cache
 WHERE (content_hash, model_key) IN (
   SELECT content_hash, model_key
     FROM embedding_cache
     ORDER BY last_hit_at ASC
     LIMIT :n_to_delete
 )
```
Run in batches.

---

#### `[ ]` I-074 🟡 Rate-limit `EXPIRE` resets TTL on every hit

**File:** `api/bigrag/middleware/rate_limit.py:157-171`

Every request bumps the counter and resets the TTL to `window_seconds * 2`. A
sustained stream keeps pushing the expiry forward and can leak counts across
window boundaries.

**Fix:** `SET key 0 EX ttl NX` (only on creation), then `INCR`. Or use
`EXPIREAT` keyed to `window_start + window_seconds * 2`.

---

#### `[ ]` I-075 🟡 `_handle_event` synchronous DNS lookup blocks the listener

**File:** `api/bigrag/models/webhook.py:36-42`

`socket.getaddrinfo()` runs inside an async Pydantic validator. A slow DNS
target stalls the server.

**Fix:** `await asyncio.get_event_loop().run_in_executor(None, socket.getaddrinfo, ...)`.

---

#### `[ ]` I-076 🟡 No re-verification on preset update

**File:** `api/bigrag/routers/embedding_presets.py:117-148`

`create_preset` calls `verify_provider_credentials`. `update_preset` does not
— admin can swap to an invalid key and only learn at first embed.

**Fix:** Re-verify in `update_preset` whenever `api_key` or `provider` changes.

---

#### `[ ]` I-077 🟡 `_recursive_chunks` offset arithmetic is technically correct but fragile

**File:** `api/bigrag/services/ingestion.py:149-168`

`cursor` and `start_offset` accounting is correct on inspection — but the
absolute-vs-relative offset logic is easy to break in future edits. Add a
docstring explaining the invariant, plus a unit test that round-trips a few
known offsets.

---

#### `[ ]` I-078 🟡 `mcp_server` raw 5xx detail forwarded to MCP client

**Files:** `api/bigrag/mcp_server.py:46-54`,
`api/bigrag/services/mcp_http.py:78-86`

```python
raise RuntimeError(f"bigRAG {response.status_code}: {detail}")
```

`detail` is upstream JSON, possibly containing internal stack traces or paths.

**Fix:** Pass `detail` through only for 4xx responses; map 5xx to a generic
`"upstream server error"` message.

---

#### `[ ]` I-079 🟡 DNS rebinding with `enable_dns_rebinding_protection=False`

**File:** `api/bigrag/services/mcp_http.py:106-109`

OK for HTTPS deployments where auth is bearer-token. Local dev (`host=0.0.0.0`,
no TLS) is vulnerable: an attacker domain rebinds to `127.0.0.1` and the
browser hits `/mcp` cross-origin.

**Fix:** Conditionally enable DNS rebinding protection when `env != "prod"` and
the server is bound to a non-loopback interface. Or always validate `Origin`
for non-HTTPS deployments.

---

#### `[ ]` I-080 🟡 `sslmode=disable` stripping is fragile

**File:** `api/bigrag/db/engine.py:22-24`

Doesn't handle `sslmode=disable&other=...` (mid-string) — strips it but leaves
a leading `?&` which asyncpg rejects.

**Fix:** Use `urllib.parse.urlparse` / `parse_qs` and strip `sslmode` properly.

---

#### `[ ]` I-081 🟡 `_SENSITIVE_KEYS` missing `secret` and `master_key`

**File:** `api/bigrag/logging.py:9-31`

`Webhook.secret` is the column name. `Settings.master_key` is the field. Both
absent from the redaction set. If anything ever logs a model `__dict__` or a
settings dump, those values land in logs.

**Fix:** Add `"secret"` and `"master_key"` to `_SENSITIVE_KEYS`.

---

#### `[ ]` I-082 🟡 Path normalization in request logger

**File:** `api/bigrag/logging.py:141`

ASGI loopback transport doesn't sanitize path values before passing to the
scope. A tool body building paths with user-supplied collection names that
contain `\n` produces log lines with embedded newlines (log forging).

**Fix:** `path = scope["path"].replace("\r", "").replace("\n", "")` before
logging. And validate collection / document_id at the tool boundary (see
I-063).

---

#### `[ ]` I-083 🟡 Dockerfile entrypoint is `python -m bigrag.main`

**File:** `api/Dockerfile:65`

Bypasses the installed `bigrag` console script. Uvicorn `factory=True` workers
inherit `sys.argv[0]` which is `bigrag.main` instead of the script — works,
but unusual and breaks some uvicorn reload paths.

**Fix:** `ENTRYPOINT ["bigrag"]` (the project script defined in
`pyproject.toml`).

---

#### `[ ]` I-084 🟡 No upper-bound deps and no lockfile

**File:** `api/pyproject.toml:7-29`

`mcp>=1.12.0` is the most fragile — `FastMCP` API has churned across minors.
A `mcp==2.0` release silently breaks the build.

**Fix:** Cap majors (`mcp<2`, `fastapi<1`, etc.) and commit `uv.lock` to the
repo so Docker builds are reproducible.

---

#### `[ ]` I-085 🟡 Idempotency middleware doesn't bound the cached body size

**File:** `api/bigrag/middleware/idempotency.py:84-114`

The middleware stores the entire response body in Redis (latin-1 encoded) for
24 hours. A 1 GB upload that returns a small JSON is fine; a streaming
response or large response body could blow up Redis.

**Fix:** Bound the cached body by Content-Length; skip caching responses
larger than e.g. 64 KB.

---

#### `[ ]` I-086 🟡 `useCollectionStats` polls every 10 s with cache stacking

**File:** `app/src/hooks/use-collections.ts:26-33`

`refetchInterval: 10_000` always on. With `gcTime: 60_000`, recently
unmounted observers continue firing for up to 60 s. Multiple mounts (sidebar
badge + detail panel) stack independently.

**Fix:** Tie polling to component visibility:
```ts
refetchInterval: (query) => query.state.status === 'success' ? 10_000 : false,
refetchIntervalInBackground: false,
```

---

## SDK drift & inconsistency

#### `[ ]` I-087 🟠 Rust `WebhookListResponse.total` will panic at runtime

**File:** `sdks/rust/src/types/webhooks.rs:73-78`

Server returns `{"webhooks": [...]}` — no `total`. The Rust struct requires
it. `serde_json` returns `missing field 'total'` for every `webhooks.list()`
call.

**Fix:** Remove `total` from the struct, or make it `Option<u32>` with
`#[serde(default)]`.

---

#### `[ ]` I-088 🟠 Rust `S3Job` missing `endpoint_url` and `metadata`

**File:** `sdks/rust/src/types/documents.rs:168-195`

Server always serializes both. Missing → deserialization panic on
`list_s3_jobs` and `ingest_s3` responses.

**Fix:** Add `pub endpoint_url: Option<String>` and `pub metadata:
serde_json::Value` (with `#[serde(default)]`).

---

#### `[ ]` I-089 🟠 Rust `StatusResponse.message` non-optional

**File:** `sdks/rust/src/types/common.rs:5-10`

Server omits `message` on 204 No Content paths. Deserialization panics.

**Fix:** `pub message: Option<String>` with `#[serde(default)]`.

---

#### `[ ]` I-090 🟠 Rust `get_stream` sends API key both in URL and header

**File:** `sdks/rust/src/core.rs:126-150`

URL `?token=` _and_ `Authorization: Bearer …`. Double-leak via access logs.
TS and Python use one mechanism.

**Fix:** Drop the URL token; rely on `Authorization` (server accepts it for
SSE).

---

#### `[ ]` I-091 🟠 SDK type drift: `Document` missing `content_hash`, `deduped`

**Files:**
- `sdks/typescript/src/types/documents.ts:1-14`
- `sdks/python/src/bigrag/types/documents.py:8-19`
- `sdks/rust/src/types/documents.rs:4-28`

Server `DocumentResponse` includes both. The `deduped: true` flag is the only
way callers can detect dedup. SDK callers cannot.

**Fix:** Add the two fields to all three SDK types.

---

#### `[ ]` I-092 🟠 SDK type drift: `QueryResponse` missing `timings`, `facets`, `cached`

**Files:**
- `sdks/typescript/src/types/query.ts:22-27`
- `sdks/python/src/bigrag/types/query.py:26-30`
- `sdks/rust/src/types/query.rs:55-65`

`QueryResult` is also missing `page_no`, `char_start`, `char_end` (citation
provenance).

**Fix:** Add all six fields across the three SDK types.

---

#### `[ ]` I-093 🟠 SDK type drift: `QueryBody` missing 5 request fields

**Files:** all three SDK `types/query.*`

Server accepts `diversity`, `hybrid_strategy`, `hyde`, `facets`,
`use_semantic_cache`. None of the SDKs declare them.

**Fix:** Add all five as optional fields.

---

#### `[ ]` I-094 🟠 SDK type drift: `MultiQueryBody` missing `rerank` (Python+TS)

**Files:**
- `sdks/python/src/bigrag/types/query.py:33-40`
- `sdks/typescript/src/types/query.ts:29-37`

Rust correctly has it.

**Fix:** Add `rerank: NotRequired[bool]` (Python) and `rerank?: boolean` (TS).

---

#### `[ ]` I-095 🟠 SDKs missing endpoints

| Endpoint | TS | Python | Rust |
|---|---|---|---|
| `POST /v1/collections/{name}/reembed` | ❌ | ❌ | ❌ |
| `POST /v1/admin/webhooks/{id}/deliveries/{did}/replay` | ❌ | ❌ | ❌ |
| `/v1/admin/mcp-servers/*` | ❌ | ❌ | ❌ |
| `/v1/admin/users/*` | ❌ | ❌ | ❌ |
| `/v1/admin/audit` | ❌ | ❌ | ❌ |
| `/v1/admin/embedding-presets/*` | ❌ | ❌ | ❌ |
| `/v1/usage` | ❌ | ❌ | ❌ |
| `/v1/admin/eval` | ❌ | ❌ | ❌ |
| `get_s3_job` / `update_s3_job` | ✅ | ❌ | ❌ |
| Pagination on `get_chunks` | ✅ | ❌ | ✅ |

**Fix:** Decide on coverage policy (admin-only routes via SDKs are arguably
fine to skip, but document it). Add `reembed` and `replay_delivery` to all
three. Bring Python's `get_chunks` up to par.

---

#### `[ ]` I-096 🟠 Python SDK: `typing_extensions` not declared

**File:** `sdks/python/pyproject.toml`

`_compat.py` imports from `typing_extensions` when `sys.version_info < (3,
11)`. `pyproject.toml` claims `requires-python = ">=3.10"` but doesn't depend
on `typing_extensions`. On a bare Python 3.10 env: `ModuleNotFoundError`.

**Fix:**
```toml
dependencies = [
    "httpx>=0.28.0",
    "httpx-sse>=0.4.0",
    "typing_extensions>=4.0; python_version < '3.11'",
]
```

---

#### `[ ]` I-097 🟠 Python SDK: `_request_form` files quirk

**File:** `sdks/python/src/bigrag/resources/documents.py:86`

```python
files=dict(file_list) if len(file_list) == 1 else file_list,
```

Pointless conditional that hides the type error noted in the comment. Just
always pass the list of `("files", (name, data))` tuples.

**Fix:**
```python
files=file_list,
```

---

#### `[ ]` I-098 🟠 Python SDK: `get_chunks` silently truncates at 50

**File:** `sdks/python/src/bigrag/resources/documents.py:130-136`

No `limit`/`offset` parameters. Server defaults to 50. Documents with > 50
chunks silently truncate.

**Fix:** Add `limit: int | None = None, offset: int | None = None`, forward
them.

---

#### `[ ]` I-099 🟠 SDK type drift: Python+Rust `Update/CreateCollectionBody`

**Files:** `sdks/python/src/bigrag/types/collections.py`,
`sdks/rust/src/types/collections.rs`

Missing `embedding_preset_id`, `embedding_base_url`, `chunk_strategy`,
`index_type`, `tenant_field`, `metadata_schema`, `redact_pii`,
`moderation_enabled` (create). Same set on update.

**Fix:** Add all fields. Confirm against `api/bigrag/models/collection.py`.

---

#### `[ ]` I-100 🟡 SDK SSE parsers swallow JSON errors

**Files:** `sdks/typescript/src/sse.ts:25-26`,
`sdks/python/src/bigrag/_sse.py:26-29`,
`sdks/rust/src/sse.rs:33`

Bare `catch {}` / `except`. Caller has no way to detect malformed events.

**Fix:** At minimum log a warning. Optionally surface as a typed
`ParseError`.

---

#### `[ ]` I-101 🟡 TS SSE parser doesn't accumulate multi-line `data:` blocks

**File:** `sdks/typescript/src/sse.ts:17-27`

Splits on `\n` per-line; SSE spec allows multi-line `data:` events
concatenated by `\n`. Server currently emits single-line JSON, but if any
field ever serializes with embedded newlines, frames are silently dropped.

**Fix:** Buffer until `\n\n`, then process the block. The Rust parser
already does it correctly.

---

#### `[ ]` I-102 🟡 Rust `CollectionClient::analytics` doesn't url-encode

**File:** `sdks/rust/src/client.rs:344-348`

```rust
let path = format!("/v1/collections/{}/analytics", &self.name);
```

All other `CollectionClient` methods route through resource methods that call
`urlencode`. This one is hand-rolled.

**Fix:** `format!("/v1/collections/{}/analytics", urlencode(&self.name))`.

---

#### `[ ]` I-103 🟡 TS `_requestFormData` doesn't guard 204 / empty bodies

**File:** `sdks/typescript/src/core.ts:228-243`

`response.json()` is unconditional. A 204 will throw `SyntaxError`.

**Fix:** Mirror the 204 guard from `_request`.

---

#### `[ ]` I-104 🟡 Python SDK: `_sse.py` imports via barrel

**File:** `sdks/python/src/bigrag/_sse.py:10`

```python
from bigrag._types import ProgressEvent
```

`_types` is a `from bigrag.types import *` re-export. Layering inversion: a
private module imports via a public barrel. If the barrel changes, this
breaks.

**Fix:** `from bigrag.types.sse import ProgressEvent`.

---

## Docs / drift cleanup

#### `[ ]` I-105 🟡 README MCP tool list says 6, code exposes 8

**File:** `README.md:287`

Full-workspace keys see 8 tools (adds `get_collection_stats` and
`multi_collection_query`). README hasn't been updated.

**Fix:** Update the README list to match `mcp_server.py` and
`docs/sdks/mcp.mdx`.

---

#### `[ ]` I-106 🟡 README database URL default mismatches Docker default

**Files:** `README.md:297`, `docker-compose.yml:15`,
`website/content/docs/deployment/docker.mdx:130`

README env-var table shows `localhost:5433` (the bare-metal/dev default).
docker-compose overrides to `postgres:5432`. New users copying the README
table for a Docker deployment hit a connection-refused.

**Fix:** Add a parenthetical noting the Docker internal port, or split into
two rows.

---

#### `[ ]` I-107 🟡 OpenRAG gap analysis — multiple stale claims

**File:** `website/content/docs/openrag-gap-analysis.mdx`

- §7.2 / matrix line 717: claims no MCP server (it ships).
- §8.5 / matrix line 712: claims no audit trail (full audit log exists).
- §6.2 / matrix line 703-704: contradicts itself on structlog.
- §5.7 line 451-454: claims "no user-level roles" — admin/member roles exist
  with DB-level CHECK.
- §11 Tier 2 item 7: still recommends building per-user API keys, but §5.4
  marks them resolved.

**Fix:** Pass over the doc, mark each gap "Resolved" or remove.

---

#### `[ ]` I-108 🟡 `comparison.mdx` matrix says "Web UI: No"

**File:** `website/content/docs/comparison.mdx:23`

Studio ships in `app/`. The body of the page acknowledges this; the
at-a-glance matrix doesn't.

**Fix:** "Yes (Studio)" or "Optional (Studio)".

---

#### `[ ]` I-109 🟡 `embedding-presets.mdx` lists `openai_compatible` as a valid provider

**Files:** `website/content/docs/api-reference/embedding-presets.mdx:50-55`,
`api/bigrag/models/embedding_preset.py:11`,
`api/bigrag/db/models.py:309-313`

DB CHECK and Pydantic regex both restrict to `openai|cohere`. Doc claims
three options. Either the model needs to widen, or the doc needs to narrow.

**Fix:** Narrow the doc (presets are a shortcut for the two managed
providers; `openai_compatible` is configured inline on the collection).

---

#### `[ ]` I-110 🟡 `collections.mdx` UpdateCollectionRequest table lists fields the route doesn't write

**Files:** `website/content/docs/api-reference/collections.mdx:173-178`,
`api/bigrag/routers/collections.py:371-395`

`metadata_schema`, `redact_pii`, `moderation_enabled`, `chunk_strategy` are
documented as putable, accepted by the Pydantic model — and never assigned
in the handler. Sending them is a no-op.

**Fix:** Implement the missing assignments in `update_collection`. (Don't
just delete from the doc — the model accepts them, so users will rightly
expect them to work.)

---

#### `[ ]` I-111 🟡 `collections.mdx` example response includes `embedding_base_url`

**File:** `website/content/docs/api-reference/collections.mdx:36`

`CollectionResponse` Pydantic model omits `embedding_base_url`. Example
response shouldn't include it.

**Fix:** Remove from example, or add to `CollectionResponse`.

---

#### `[ ]` I-112 🟡 Webhook admin docs say session-only; code uses `require_admin`

**Files:** `website/content/docs/concepts/security.mdx:38-46`,
`api/bigrag/routers/webhooks.py`

Same drift on `/v1/admin/embedding-presets`.

**Fix:** Decide which is correct and align the other side.

---

#### `[ ]` I-113 🟡 `studio.mdx` route map vs `app/src/app/`

**File:** `website/content/docs/studio.mdx`

Verify every route listed exists. `/mcp` exists; `/models` exists;
`/api-keys` exists; `/playground` exists. Looks correct, but worth
confirming after every Studio refactor.

---

#### `[ ]` I-114 🟡 `docker.mdx` snippet omits `milvus.yaml` mount

**Files:** `website/content/docs/deployment/docker.mdx:91-102`,
`docker-compose.yml:118`

Real compose file mounts `./milvus.yaml:/milvus/configs/user.yaml:ro`. Doc
example doesn't. Operators copying the doc snippet get default Milvus
config.

**Fix:** Add the mount, or note it's omitted for brevity.

---

#### `[ ]` I-115 🟡 Encryption docs use a real-looking Fernet key as example

**Files:** `website/content/docs/deployment/encryption.mdx:42`,
`dev.sh:150`

The same string `Zm5VZ4vO8r0y3rVsT0xz7nxV_wP7u6-n5tB1GAlHZIw=` appears in
both. The `dev.sh` comment notes "DO NOT reuse in prod" — but the docs use
the same value in their example `export` line. Easy to copy into prod by
mistake.

**Fix:** Replace the docs example with an obvious placeholder
(`<paste your generated key>`) or a hash that's clearly not a Fernet key.

---

#### `[ ]` I-116 🟡 `CONTRIBUTING.md` references nonexistent `database.py`

**File:** `CONTRIBUTING.md:54`

Project tree shows `database.py` under `api/bigrag/`. Real layout is the
`db/` package.

**Fix:** Update the tree.

---

#### `[ ]` I-117 🟡 Tech-stack version drift

**Files:** `CLAUDE.md:7`, `STYLEGUIDE.md:152-153`

- `CLAUDE.md` says Next.js 16, TypeScript 5.8.
- `STYLEGUIDE.md` says Next.js 15.
- `app/package.json`: Next.js `^16.2.4`, TypeScript `^6.0.3`.

**Fix:** Reconcile to the package.json reality.

---

#### `[ ]` I-118 🟡 `bigrag.toml` is a tiny subset of the documented schema

**Files:** `bigrag.toml`,
`website/content/docs/getting-started/configuration.mdx`

Repo-root `bigrag.toml` covers `[server]`, `[database]`, `[milvus]`,
`[redis]`, `[ingestion]`. Docs example covers `[session]`, `[embedding]`,
`[storage]`, `[s3]`, `[webhooks]`. Worse: docs example puts `log_level`,
`log_format`, `cors_origins` under `[server]`, but `from_toml()` flattens
that to `server_log_level` while `Settings` reads top-level `log_level`. So
those fields, set under `[server]` per the docs, are silently ignored.

**Fix:**
- Promote `log_level`, `log_format`, `cors_origins` to top-level keys in the
  docs example, OR
- Fix `from_toml()` to map `[server].log_level → log_level` (and similar).

---

#### `[ ]` I-119 🟡 CI is missing `test:api` and SDK tests

**File:** `.github/workflows/ci.yml`

`CONTRIBUTING.md:114` says "All CI checks must pass (lint, test, sdk-test,
website-build, biome)". Only typecheck/lint/website-build are wired up.

**Fix:**
- Add a Python test job: `uv run pytest tests/ -v` (after `uv sync --dev`).
- Add an SDK test job for the TS client (`pnpm --filter @bigrag/client test`).
- Add `pnpm build` to the `studio-build` job.
- Add a Rust SDK test job: `cargo test` in `sdks/rust/`.

---

#### `[ ]` I-120 🟡 `biome.jsonc` schema URL pinned to a specific minor

**Files:** `biome.jsonc:2`, `package.json:20`

`"$schema": "https://biomejs.dev/schemas/2.4.13/schema.json"` plus
`"@biomejs/biome": "^2.4.13"`. As soon as pnpm bumps to 2.5.x, the schema
URL is stale and editors warn.

**Fix:** Pin both exactly, or use the unpinned `…/schemas/latest/schema.json`.

---

#### `[ ]` I-121 🟢 `dev.sh` doesn't kill stale 6100 process under `--infra`

**File:** `dev.sh:60-72`

The kill block runs only when `START_BACKEND` or `START_WEBSITE` is true.
`./dev.sh --infra` skips it; an orphaned API process can survive on 6100.

**Fix:** Run the kill block whenever `START_INFRA` is true.

---

#### `[ ]` I-122 🟢 `authentication.mdx` doesn't list `/v1/auth/whoami`

**File:** `website/content/docs/api-reference/authentication.mdx:144-152`

The "which auth which endpoint" table omits `whoami`. MCP clients call it on
startup.

**Fix:** Add a row.

---

#### `[ ]` I-123 🟢 `concepts/collections.mdx` only lists 2 providers

**File:** `website/content/docs/concepts/collections.mdx:44`

Says `embedding_provider` is "openai or cohere". Code allows
`openai_compatible` too. The api-reference page is correct; the concepts
page lags.

**Fix:** Add `openai_compatible` to the concepts table.

---

## Suggested order of attack

If you want a single concrete plan, this is the order I'd land things — small
PRs, in this order:

### Sprint 1: unbreak the build

1. **I-020** Dockerfile alembic — image is dead until this lands.
2. **I-021** CI checkout@v6 → @v4.
3. **I-022** Rewrite `0001_initial_schema.py` with explicit `op.create_table`s.
4. **I-023** Cleanup task `safe_create_task` + await on cancel.

### Sprint 2: close the security holes

5. **I-001** SSRF on `endpoint_url`.
6. **I-002** Idempotency key principal scoping.
7. **I-003** Apply per-key rate limits.
8. **I-004** Re-resolve webhook URL at delivery time.
9. **I-005** Restrict query-param auth to SSE paths.
10. **I-006** Login timing oracle.
11. **I-007** `LocalStorage._safe_path`.
12. **I-008** Milvus expression escape.
13. **I-009** Content-Disposition.
14. **I-010** Proxy redirect validation.
15. **I-011** Proxy CSRF check.
16. **I-046** OpenAI key encryption-at-rest.

### Sprint 3: data-integrity bugs

17. **I-013** Heartbeat-leased queue recovery.
18. **I-014** Multi-process SSE completion.
19. **I-015** `document_count` + zero-chunk gating.
20. **I-016** S3 ingest counter lock.
21. **I-017** Blocking pymilvus calls.
22. **I-018** Semantic cache reordering.
23. **I-019** Python `_request_form` retries.

### Sprint 4: auth/scope cleanup

24. **I-024** Scope reembed + truncate.
25. **I-025** Scope global doc/chunk routes.
26. **I-026** Method-aware `_FORBIDDEN_FOR_SCOPED`.
27. **I-027** Login/setup brute-force limit.
28. **I-028** Audit webhook mutations.
29. **I-029** Stop caching `embedding_api_key` in Redis.
30. **I-030** Sanitize `/health/ready` errors.
31. **I-031** Last-admin atomic delete.
32. **I-032** `logout-all` → `require_session`.
33. **I-033** Setup 403 → 409.

### Sprint 5: SDK type sweep

34. **I-087, I-088, I-089** Rust panic-fixes.
35. **I-090** Rust `get_stream` token leak.
36. **I-091, I-092, I-093, I-094** Type drift across all three SDKs.
37. **I-095** Add `reembed`, `replay_delivery`.
38. **I-096** Python `typing_extensions`.
39. **I-097, I-098** Python upload + chunk pagination.
40. **I-099** Python+Rust collection bodies.
41. **I-100, I-101, I-102, I-103, I-104** SSE parser nits.

### Sprint 6: docs & drift

42. **I-105 – I-123** in one or two large doc PRs.

### Sprint 7: perf & code quality

43. The remaining medium-priority items as time allows.

---

## Index by file

For quick "what's outstanding in X" lookups.

### `api/bigrag/main.py`
- I-023

### `api/bigrag/config.py`
- I-058, I-059

### `api/bigrag/logging.py`
- I-081, I-082

### `api/bigrag/exceptions.py`
- (none)

### `api/bigrag/utils.py`
- (none — but referenced in I-023)

### `api/bigrag/middleware/auth.py`
- I-005, I-067, (I-068 partial)

### `api/bigrag/middleware/rate_limit.py`
- I-003, I-027, I-068, I-074

### `api/bigrag/middleware/idempotency.py`
- I-002, I-085

### `api/bigrag/services/queue.py`
- I-013, I-015, I-050, I-051, I-054

### `api/bigrag/services/event_bus.py`
- I-014

### `api/bigrag/services/webhook.py`
- I-004, I-048, I-049

### `api/bigrag/services/vector_store.py`
- I-008, I-017, I-047

### `api/bigrag/services/embedding.py`
- I-053, I-054, I-064

### `api/bigrag/services/embedding_cache.py`
- I-073

### `api/bigrag/services/semantic_cache.py`
- I-055

### `api/bigrag/services/conversion.py`
- I-052

### `api/bigrag/services/storage.py`
- I-007

### `api/bigrag/services/s3_ingest.py`
- I-016, I-056

### `api/bigrag/services/audit.py`
- I-068

### `api/bigrag/services/crypto.py`
- I-029, I-070

### `api/bigrag/services/mcp_http.py`
- I-062, I-063, I-079

### `api/bigrag/services/moderation.py`
- I-066

### `api/bigrag/mcp_server.py`
- I-063, I-078

### `api/bigrag/services/scopes.py`
- I-024, I-025

### `api/bigrag/services/collection_scope.py`
- I-026

### `api/bigrag/routers/auth.py`
- I-006, I-032, I-033

### `api/bigrag/routers/admin_users.py`
- I-031

### `api/bigrag/routers/webhooks.py`
- I-028, I-112 (drift with docs)

### `api/bigrag/routers/embedding_presets.py`
- I-076

### `api/bigrag/routers/collections.py`
- I-110 (route doesn't write some fields)

### `api/bigrag/routers/documents.py`
- I-001, I-009, I-065, I-071, I-072

### `api/bigrag/routers/health.py`
- I-017, I-030

### `api/bigrag/routers/query.py`
- I-018

### `api/bigrag/db/base.py`
- I-060

### `api/bigrag/db/engine.py`
- I-057, I-080

### `api/bigrag/db/models.py`
- I-061, I-029 (UserPreference encryption — see also I-046)

### `api/alembic/versions/0001_initial_schema.py`
- I-022

### `api/Dockerfile`
- I-020, I-083

### `api/pyproject.toml`
- I-084

### `app/src/app/api/bigrag/[...path]/route.ts`
- I-010, I-011, I-034, I-044, I-045

### `app/src/lib/api.ts`
- I-042

### `app/src/lib/openai-stream.ts`
- I-012

### `app/src/hooks/use-auth.ts`
- I-037, I-038

### `app/src/hooks/use-collections.ts`
- I-086

### `app/src/hooks/use-api-keys.ts`
- I-041

### `app/src/app/(dashboard)/layout.tsx`
- I-039

### `app/src/app/(dashboard)/mcp/page.tsx`
- I-005, I-035, I-036

### `app/src/app/(dashboard)/playground/components/chat-input.tsx`
- I-046

### `app/src/app/(dashboard)/webhooks/components/webhook-form.tsx`
- I-040

### `app/src/app/(auth)/login/page.tsx`
- I-043

### `app/next.config.ts`
- I-012

### `sdks/typescript/src/types/documents.ts`
- I-091

### `sdks/typescript/src/types/query.ts`
- I-092, I-093, I-094

### `sdks/typescript/src/sse.ts`
- I-100, I-101

### `sdks/typescript/src/core.ts`
- I-103

### `sdks/python/src/bigrag/types/documents.py`
- I-091

### `sdks/python/src/bigrag/types/query.py`
- I-092, I-093, I-094

### `sdks/python/src/bigrag/types/collections.py`
- I-099

### `sdks/python/src/bigrag/resources/documents.py`
- I-097, I-098

### `sdks/python/src/bigrag/_core.py`
- I-019

### `sdks/python/src/bigrag/_sse.py`
- I-100, I-104

### `sdks/python/pyproject.toml`
- I-096

### `sdks/rust/src/types/documents.rs`
- I-088, I-091

### `sdks/rust/src/types/query.rs`
- I-092, I-093

### `sdks/rust/src/types/collections.rs`
- I-099

### `sdks/rust/src/types/webhooks.rs`
- I-087

### `sdks/rust/src/types/common.rs`
- I-089

### `sdks/rust/src/core.rs`
- I-090

### `sdks/rust/src/client.rs`
- I-102

### `sdks/rust/src/sse.rs`
- I-100

### `README.md`
- I-105, I-106

### `CLAUDE.md`
- I-117

### `STYLEGUIDE.md`
- I-117

### `CONTRIBUTING.md`
- I-116

### `dev.sh`
- I-115, I-121

### `bigrag.toml`
- I-118

### `biome.jsonc`
- I-120

### `.github/workflows/ci.yml`
- I-021, I-119

### `website/content/docs/concepts/security.mdx`
- I-112

### `website/content/docs/concepts/collections.mdx`
- I-123

### `website/content/docs/api-reference/authentication.mdx`
- I-033, I-122

### `website/content/docs/api-reference/collections.mdx`
- I-110, I-111

### `website/content/docs/api-reference/embedding-presets.mdx`
- I-109

### `website/content/docs/comparison.mdx`
- I-108

### `website/content/docs/openrag-gap-analysis.mdx`
- I-107

### `website/content/docs/deployment/docker.mdx`
- I-114

### `website/content/docs/deployment/encryption.mdx`
- I-115

### `website/content/docs/getting-started/configuration.mdx`
- I-118

---

## Notes for future passes

- Several agent findings I dropped because the reasoning was wrong:
  - "`hmac.new` doesn't exist" — it does, both as a top-level alias and via
    `hmac.HMAC`.
  - "`asyncio.run` inside a thread-pool worker would fire 'event loop
    already running'" — that thread has no running loop; the call is fine.
    The real concern (advisory lock not held against the right session)
    persists but is a narrower issue than the agent flagged.
- A few items overlap (e.g. token-in-URL appears in I-005, I-035, I-062);
  treat them as the same logical fix touching three surfaces.
- The `app/` agent confused itself in places about React DOM rendering vs
  text-node rendering. The token-in-DOM concern (I-035) is real because
  `<pre><code>{redacted-or-not}</code></pre>` lands the value in DOM text;
  the chunk-rendering concern is fine because React escapes by default.
- Sprint 2 (security) is the riskiest if you're shipping to real users
  today. Sprint 1 (unbreak) is the most embarrassing if anyone tries the
  documented Docker quickstart.

