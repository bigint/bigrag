# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Turbopuffer vector search)
- `sdks/typescript/` — TypeScript SDK (`@bigrag/client`)
- `sdks/python/` — Python SDK (`bigrag`)
- `app/` — admin UI (Vite + TanStack Router + Tailwind v4 + Base UI, `@bigrag/app`)
- `website/` — Documentation site (Next.js + Fumadocs, content in `website/content/docs/`)

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

### No comments

Don't write comments or docstrings in code under `api/bigrag/`, `sdks/typescript/src/`, `sdks/python/src/`, `app/`, or `website/`. This includes `#`, `//`, `/* */`, `/** */` JSDoc, and Python `"""docstrings"""`. The diff and well-named identifiers should speak for themselves; surprising invariants belong in commit messages or PR descriptions, not in the code. The only allowed exceptions are functional directives — shebangs, `# type: ignore`, `# noqa`, `# ruff:`, `// @ts-…`, `// biome-ignore`, `// eslint-…`, and similar tool pragmas, plus Pydantic `Field(description="...")` strings that are load-bearing for OpenAPI.

If you find yourself wanting to explain code, rename or restructure it instead.

### One thing per file

The repo follows aggressive package-style splits. If a single file grows past ~300 LoC, look for a clean seam (per-handler, per-provider, per-stage) and split into a package directory. Examples already shipped:

- `api/bigrag/db/models/` (per domain: auth, collection, connector, document, instance, observability, preference, webhook)
- `api/bigrag/app_factory/` (lifespan, exception_handlers, routers)
- `api/bigrag/mcp/` (tools, unscoped, scoped, cli)
- `api/bigrag/services/{embedding,retrieval,webhook,vector_store,storage,url_security,access_log,event_bus,queue_conversion,queue_embedding,chat,runtime_setting_specs}/` packages
- `sdks/python/src/bigrag/resources/admin/` and `sdks/typescript/src/resources/admin/` (settings, users, api_keys, access, audit, connectors, embedding_presets, mcp_servers, vector_storage)

When adding new code, prefer the smallest meaningful module instead of dropping it into the nearest catch-all.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, docling, openai, cohere, cryptography (Fernet for at-rest encryption of provider secrets), dramatiq (Redis broker)
- **Vector DB**: Turbopuffer
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, XLSX, HTML, Markdown, images)
- **Embedding**: OpenAI, Cohere, Voyage, and OpenAI-compatible providers
- **Caching/queues**: Redis (auth principal cache, embedding cache, dramatiq ingestion + webhook queues)

## Package Management

- **Python backend**: `uv` (lockfile at `api/uv.lock`)
- **Python SDK**: `uv` (lockfile at `sdks/python/uv.lock`)
- **TypeScript SDK + Website + App**: `pnpm` workspaces (root `pnpm-workspace.yaml`)

**Gotcha**: `pnpm-workspace.yaml` sets `minimumReleaseAge: 10080` (7 days). Any `pnpm install` that triggers a fresh dependency resolution may fail for packages published in the last week (commonly rolldown, rollup, and @tanstack platform binaries). Either wait, or add the offending name to `minimumReleaseAgeExclude:`.

## Linting

- **Python**: `ruff` (config in `api/pyproject.toml`)
- **TypeScript/JS**: `biome` (config in `biome.jsonc`)

**Always run lint + format before committing.** Either let the pre-commit hook run them, or invoke them manually — never commit unformatted code:

```bash
# Python (api/)
cd api && uv run ruff check --fix .
cd api && uv run ruff format .

# Python SDK
uv run --project api ruff check --fix sdks/python/src
uv run --project api ruff format sdks/python/src

# TS / JS / JSON / CSS (everything else)
pnpm exec biome check --write .
```

### Pre-commit hook

The repo ships a `.pre-commit-config.yaml` that runs `ruff check`, `ruff format`, and `biome check` on staged files. Install it once per clone:

```bash
uv tool install pre-commit   # or: brew install pre-commit
pre-commit install
```

After that, every `git commit` runs the same formatters for API Python and TS/JS/CSS files that CI enforces. Run package build/typecheck commands manually when touching SDKs. **NEVER skip hooks with `--no-verify`.** If a hook auto-fixes a file, the commit aborts — re-stage and commit again.

## Verification

The old package-level unit/integration suites, end-to-end suites, and coverage commands have been removed. Do not add package test runners, end-to-end test runners, or coverage requirements back to feature work unless the project reintroduces them deliberately.

Use lint, typecheck, build, compile, and runtime smoke checks for current verification. Keep `website/content/docs/development/testing.mdx` in sync when verification guidance changes, and do not commit generated coverage artifacts.

## Architecture Notes

- Backend uses FastAPI dependency injection via `bigrag/db/session.py::get_session` and `bigrag.middleware.auth::get_current_user` / `require_admin_session`.
- Database layer lives in `bigrag/db/`: `engine.py` (async engine), `session.py` (FastAPI `get_session` dependency), `models/` (ORM models, split by domain), `bootstrap.py` (stamp-or-upgrade on startup). Schema changes go through Alembic (`api/alembic/`). Migrations are collapsed into a single `0001_initial_schema.py` — re-emit (do not stack new revisions) when models change, and run `alembic revision --autogenerate -m drift_check` to confirm no drift.
- The user-session ORM model is `UserSession` (table `sessions`) — not `Session`, which would clash with SQLAlchemy's own session class.
- App factory: `api/bigrag/app_factory/{lifespan,exception_handlers,routers}.py` assembled by `bigrag/main.py::create_app()`.
- Services are organized by domain under `api/bigrag/services/` — most non-trivial ones are packages (`embedding/`, `retrieval/`, `webhook/`, `vector_store/`, `storage/`, `url_security/`, `access_log/`, `event_bus/`, `queue_conversion/`, `queue_embedding/`, `chat/`, `runtime_setting_specs/`).
- Tenant scoping: route handlers call `enforce_collection_pin(user, collection_name)` from `routers/__init__.py` to honor pinned API keys. Connector accounts/sources carry an optional `tenant_id` column.
- Background workers: Dramatiq actors live in `services/jobs/`. The ingestion queue (`services/queue.py`) drains via `bigrag-worker`.
- MCP server: `api/bigrag/mcp/` package (`tools`, `unscoped`, `scoped`, `cli`); entry point `bigrag-mcp = "bigrag.mcp:cli"`.
- SDK uses resource namespaces: `client.collections.list()`, `client.documents.upload()`, `client.admin.users.list()` etc. The `admin` resource is itself a package — sub-resources live in `resources/admin/{settings,users,api_keys,access,audit,connectors,embedding_presets,mcp_servers,vector_storage}.py`.
- SDK reliability: both Python and TypeScript SDKs send `Idempotency-Key: <uuid4>` on POST/PUT/PATCH/DELETE and only retry mutating calls when an idempotency key is present. Both expose typed error subclasses (`BadRequestError`, `ConflictError`, `PayloadTooLargeError`, `UnprocessableEntityError`, `BadGatewayError`, `ServiceUnavailableError`, etc.).

## Code conventions

- **Errors to clients**: never `detail=str(exc)` — use `safe_error_detail(exc, fallback)` from `services/error_sanitize.py`. For persisted error messages (`Document.error_message`, `ConnectorSource.last_error`, SSE error frames), use `sanitize_message_text(...)` so secrets/URLs/exception internals never leak.
- **`uuid_or_404(value, label)`**, **`decode_cursor_or_400(cursor)`**, **`ensure_embedding_or_400(collection)`**, **`verify_or_422(...)`**, **`is_mcp_key(key)`**, **`enforce_collection_pin(user, name)`** are canonical helpers — use them instead of inlining the patterns.
- **CHECK constraints** go in `__table_args__`, not inline on `mapped_column(sa.CheckConstraint(...))`, so Alembic autogenerate picks them up.
- **No `routers → services → routers` imports.** Helpers that services need live in `api/bigrag/services/`, not `api/bigrag/routers/`.

## Documentation

**Always update the docs site when making any code change.** This includes adding, updating, or removing features, endpoints, models, config options, SDK methods, or CLI flags. The docs live in `website/content/docs/` as `.mdx` files.

Pages to keep in sync:

- `api-reference/` — endpoint signatures, request/response schemas, error codes
- `concepts/` — feature explanations, examples, and curl snippets
- `sdks/typescript.mdx`, `sdks/python.mdx`, `sdks/mcp.mdx` — SDK method signatures and usage
- `getting-started/configuration.mdx` — environment variables and TOML options
- `deployment/` — Docker Compose snippets and production settings
- `comparison.mdx` — if a new feature is a differentiator vs competitors

If a feature is removed, remove it from the docs too. Never leave stale references.

## Development

```bash
./dev.sh            # starts infra + backend + worker
./dev.sh --infra    # postgres + redis only
./dev.sh --website  # docs site only
pnpm dev:app        # admin UI on localhost:3000
```

- admin UI: http://localhost:3000 (first run → `/setup` to create admin)
- Backend API: http://localhost:4000 (Swagger docs at /docs)
- Postgres: localhost:5432
- Redis: localhost:6379

`dev.sh` only tears down the docker stack that it started — if you ran `docker compose up` separately before invoking `dev.sh`, it leaves that running on exit.

## MCP server

The `bigrag-mcp` entry point (`api/bigrag/mcp/cli.py`) wraps the REST API as MCP tools for Claude Desktop / Cursor / etc. It's an HTTP client, not an in-process bolt-on — auth is via `BIGRAG_API_KEY`. Pinned (collection-scoped) and unscoped tool surfaces live in `api/bigrag/mcp/scoped.py` and `api/bigrag/mcp/unscoped.py`; shared call helpers + HTTP plumbing in `api/bigrag/mcp/tools.py`. When adding or renaming an API endpoint that retrieval clients care about, update the matching tool surface and the docs at `website/content/docs/sdks/mcp.mdx`.

## Auth model

Auth is admin-account + session cookie (admin UI) or minted API keys (`bigrag_sk_...`, external clients). First admin is created via the admin UI's `/setup` page; subsequent admins via `/users`; API keys via `/api-keys`. There is no shared-secret env var — do not introduce one.

API keys can be pinned to a single collection (`permissions.collection`). Route handlers MUST call `enforce_collection_pin(user, collection_name)` for collection-scoped operations so a pinned key sees a 404 for any other collection. The middleware-level `enforce_collection_scope` runs first, but the route-level helper is defense-in-depth.

## Cleanup discipline

When adding a feature, also clean up what's left from the previous shape: stale imports, dead branches, comments-that-explain-code, single-callsite helpers that should be inlined, and constants/aliases nobody reads. The "no comments" + "package-style splits" + "no `routers → services → routers`" rules above only stay true if every change actively maintains them.
