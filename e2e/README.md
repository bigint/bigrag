# bigRAG E2E Test Suite

A live, end-to-end test suite that exercises every layer of bigRAG against a
real `docker compose` stack — REST API, both SDKs, and critical UI flows — at
~$0 of OpenAI spend per run.

## Why

bigRAG ships ~100 HTTP endpoints, two SDKs, and a React admin app. Without an
end-to-end harness, regressions in routing, schemas, streaming, or auth slip
out unnoticed. This suite is the safety net: one `make e2e` brings up the
stack, runs ~200 tests, and tears it down. CI runs the same target on every
PR.

OpenAI cost is eliminated by routing `BIGRAG_EMBEDDING_*` and `BIGRAG_CHAT_*`
at a small in-cluster fake (`fake-openai`).

## Prerequisites

- Docker / Docker Compose v2
- [uv](https://docs.astral.sh/uv/) for Python
- [pnpm](https://pnpm.io/) for TypeScript / Playwright
- Playwright browsers: `pnpm run playwright:install`

## Quick start

```bash
cd e2e
make install   # uv sync + pnpm install
make e2e       # up, test, down
```

## Make targets

| Target         | What it does                                                       |
|----------------|--------------------------------------------------------------------|
| `make up`      | Brings up the e2e compose stack and waits for `/health/ready`      |
| `make down`    | Tears down the stack and removes volumes                           |
| `make logs`    | Tails compose logs                                                 |
| `make install` | `uv sync` + `pnpm install`                                         |
| `make test-api`| Runs API pytest suite                                              |
| `make test-sdk-py` | Runs Python SDK pytest suite                                   |
| `make test-sdk-ts` | Runs TypeScript SDK vitest suite                               |
| `make test-ui` | Runs Playwright UI suite                                           |
| `make test`    | All four suites (api + sdk-py + sdk-ts + ui)                       |
| `make e2e`     | `up` → `test` → `down` (full end-to-end run)                       |

## Architecture

```
        +--------------------+
        |  pytest / vitest / |
        |  playwright        |
        +----------+---------+
                   |
        host:4000  v  host:3000        host:9001/9002/9003
   +---------------+----------+   +-----------------------------+
   |  bigrag-api  |  bigrag-ui|   | fake-openai | fake-gdrive | |
   |  bigrag-worker            |  | webhook-sink                |
   +--+----+-------+-----+-----+   +-----------------------------+
      |    |       |     |             ^         ^         ^
      v    v       v     v             |         |         |
  postgres redis qdrant  +-------------+---------+---------+
                          (bigrag-api routes embeddings, chat,
                           Google Drive connector, and webhook
                           deliveries at these local fakes)
```

The fakes live in `stubs/`:

- `fake-openai` — OpenAI-compatible `/v1/embeddings`, `/v1/chat/completions`
  (non-stream + SSE), `/v1/models`. Deterministic embeddings via
  sha256-seeded numpy RNG; canned chat responses.
- `fake-gdrive` — Mock OAuth (`/o/oauth2/*`) + Drive (`/drive/v3/*`) for the
  Google Drive connector tests.
- `webhook-sink` — Records every incoming webhook delivery; tests poll
  `/received?label=...` to assert.

## Cost

| Mode                              | Approx cost per run |
|-----------------------------------|---------------------|
| `make e2e` (default)              | $0 — everything goes through `fake-openai` |

To prove zero leakage, the suite includes a network assertion that no
request reaches `api.openai.com`.

## Test layout

```
e2e/tests/
├── api/                 # REST endpoint coverage (pytest + httpx)
├── sdk_python/          # Python SDK (`bigrag`) contract tests
├── sdk_typescript/      # TypeScript SDK (`@bigrag/client`) vitest suite
└── ui/                  # Playwright specs (10 critical flows)
```

## Adding a new test

All Python suites share fixtures from `e2e/conftest.py`:

| Fixture            | What it gives you                                     |
|--------------------|-------------------------------------------------------|
| `api_base_url`     | Base URL of the running API                           |
| `unauth_client`    | A clean `httpx.AsyncClient` with no auth              |
| `admin_setup`      | Session-scoped — guarantees the admin exists          |
| `admin_client`     | Authenticated session client (cookies + Origin set)   |
| `api_key`          | Factory: mints + revokes an API key                   |
| `api_key_client`   | Factory: `httpx.AsyncClient` with `Authorization`     |
| `collection`       | Factory: creates + deletes a uniquely-named collection|
| `document`         | Factory: uploads a fixture file and polls until ready |
| `webhook_sink_url` | Helper to address `webhook-sink/webhook/<label>`      |
| `gdrive_oauth_helper` | Helper to simulate the fake-gdrive OAuth flow     |
| `sse_events`       | Async generator over `httpx-sse`                      |

See `e2e/conftest.py` and `e2e/tests/_helpers.py` for the full contract.

Collection names are short — `e2e_<8 hex>` — so they fit Qdrant's collection
name limit. Each fixture cleans up in teardown so the suite is safe under
`pytest-xdist -n auto`.

## Coverage

| Layer            | Files | Tests |
|------------------|-------|-------|
| API (pytest)     | 28    | ~400  |
| Python SDK       | 7     | 59    |
| TypeScript SDK   | 6     | 47    |
| Playwright UI    | 10    | 15    |

**Endpoint coverage:** 121 / 121 declared `@router.*` decorators across
`api/bigrag/routers/` are exercised by at least one test path.

Audit it yourself:

```bash
python3 - <<'PY'
import os, re, glob
prefix_re = re.compile(r'APIRouter\([^)]*prefix\s*=\s*["\'']([^"\'']+)["\'']', re.S)
endpoint_re = re.compile(
    r'@(?:router|app|global_router)\.(get|post|put|patch|delete|head|options)\(\s*["\'']([^"\'']*)["\'']',
    re.IGNORECASE,
)
test_text = ""
for d in ("e2e/tests/api","e2e/tests/sdk_python","e2e/tests/ui","e2e/tests/sdk_typescript"):
    for fn in glob.glob(f"{d}/**/*", recursive=True):
        if os.path.isfile(fn) and fn.endswith(('.py','.ts')):
            with open(fn) as f: test_text += f.read()+"\n"
missing = []
total = 0
for fn in sorted(glob.glob("api/bigrag/routers/*.py")):
    base = os.path.basename(fn)
    if base.startswith("_") or base == "__init__.py": continue
    text = open(fn).read()
    pm = prefix_re.search(text); prefix = pm.group(1) if pm else ""
    for method, path in endpoint_re.findall(text):
        total += 1
        full = (prefix+path).replace("//","/")
        if not full.startswith("/"): full = "/"+full
        pat = re.sub(r"\\\{[^}]+\\\}", r"\\{[^/\"'`}]+\\}", re.escape(full))
        if not re.search(pat, test_text):
            missing.append((base, method.upper(), full))
print(f"{total - len(missing)} / {total} endpoints covered")
for m in missing: print("  MISS:", *m)
PY
```

## Known limitations

Three bigRAG behaviors bypass the fake servers because they have hardcoded
upstream URLs. They're called out so test coverage of the relevant happy
paths is "best effort" rather than full:

1. **`POST /v1/auth/preferences`** with key `chat.openai_key` validates the
   value against `api.openai.com` (provider literal is `"openai"`, not
   `"openai_compatible"`). `test_preferences.py` round-trips other keys to
   avoid this network call.
2. **Google Drive connector OAuth flow** (`api/bigrag/services/connectors/`)
   has hardcoded `accounts.google.com` / `googleapis.com` URLs.
   `test_connectors.py` covers CRUD, start-URL shape, and OAuth callback
   error paths; the full token-exchange happy path is skipped.
3. **Chat-suggestions in the Playwright `chat-streaming.spec.ts`** can't be
   end-to-end driven through the UI because saving an OpenAI key in
   preferences triggers (1). The spec validates the chat shell + collection
   picker instead. The API-level chat-suggestions tests in
   `tests/api/test_chat_suggestions.py` exercise the happy path because
   they bypass the preferences UI flow.

To close any of these, add a `BIGRAG_*_DEFAULT_BASE_URL` env override to the
relevant bigRAG service (e.g., `credential_check.py`,
`services/connectors/google_drive_auth.py`) and point it at the local fakes
from `docker-compose.e2e.yml`.
