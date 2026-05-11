# rag.computer Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Qdrant vector DB)
- `sdks/typescript/` — TypeScript SDK (`@rag.computer/client`)
- `sdks/python/` — Python SDK (`rag-computer`)
- `sdks/rust/` — Rust SDK (`rag-computer`)
- `app/` — admin UI (Vite + TanStack Router + Tailwind v4 + Base UI, `@rag.computer/app`)
- `website/` — Documentation site (Next.js + Fumadocs, content in `website/content/docs/`)

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

### No comments

Don't write comments or docstrings in code under `api/rag_computer/`, `sdks/typescript/src/`, `app/`, or `website/`. This includes `#`, `//`, `/* */`, `/** */` JSDoc, and Python `"""docstrings"""`. The diff and well-named identifiers should speak for themselves; surprising invariants belong in commit messages or PR descriptions, not in the code. The only allowed exceptions are functional directives — shebangs, `# type: ignore`, `# ruff:`, `// @ts-…`, `// biome-ignore`, `// eslint-…`, and similar tool pragmas. If you find yourself wanting to explain code, rename or restructure it instead.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, qdrant-client, docling, openai, cohere, cryptography (Fernet for at-rest encryption of provider secrets)
- **Vector DB**: Qdrant (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: OpenAI, Cohere, Voyage, and OpenAI-compatible providers

## Package Management

- **Python backend**: `uv` (lockfile at `api/uv.lock`)
- **Python SDK**: `uv` (lockfile at `sdks/python/uv.lock`)
- **TypeScript SDK + Website + App**: `pnpm` workspaces (root `pnpm-workspace.yaml`)
- **Rust SDK**: `cargo` (lockfile at `sdks/rust/Cargo.lock`)

## Linting

- **Python**: `ruff` (config in `api/pyproject.toml`)
- **TypeScript/JS**: `biome` (config in `biome.jsonc`)
- **Rust**: `cargo fmt` and `cargo test`

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

# Rust SDK
cargo fmt --manifest-path sdks/rust/Cargo.toml
cargo test --manifest-path sdks/rust/Cargo.toml
```

### Pre-commit hook

The repo ships a `.pre-commit-config.yaml` that runs `ruff check`, `ruff format`, and `biome check` on staged files. Install it once per clone:

```bash
uv tool install pre-commit   # or: brew install pre-commit
pre-commit install
```

After that, every `git commit` runs the same formatters for API Python and TS/JS/CSS files that CI enforces. Run SDK build/test commands manually when touching `sdks/python/` or `sdks/rust/`. If a hook auto-fixes a file, the commit aborts — re-stage and commit again.

## Testing and Coverage

Every feature, helper, and utility change must include or update tests in the package it touches. Prefer focused unit tests for helpers and utilities, route/service tests for backend behavior, resource/request tests for SDK changes, and hook/component tests for admin UI changes. Bug fixes should add a regression test that fails without the fix.

Maintain or improve package-level coverage when adding code. Run the relevant test and coverage command before handing off, and investigate coverage drops instead of accepting them silently:

```bash
# Backend API
cd api && uv run pytest tests/ --cov --cov-report=term-missing

# Python SDK
cd sdks/python && uv run pytest --cov --cov-report=term-missing

# TypeScript SDK
pnpm --filter @rag.computer/client test
pnpm --filter @rag.computer/client coverage

# Admin UI
pnpm --filter @rag.computer/app test
pnpm --filter @rag.computer/app coverage

# Rust SDK
cargo test --manifest-path sdks/rust/Cargo.toml
cargo llvm-cov --manifest-path sdks/rust/Cargo.toml --summary-only
```

If coverage tooling is unavailable, still run the package tests and call out the coverage gap in the handoff. Keep `website/content/docs/development/testing.mdx` in sync when test or coverage commands change, and do not commit generated coverage artifacts.

## Architecture Notes

- Backend uses FastAPI dependency injection via `rag_computer/deps.py` and `app.state`
- Database layer lives in `rag_computer/db/`: `engine.py` (async engine), `session.py`
  (FastAPI `get_session` dependency), `models.py` (all 13 ORM models), `bootstrap.py`
  (stamp-or-upgrade on startup). Schema changes go through Alembic (`api/alembic/`)
- Services: `event_bus.py` (SSE), `ingestion_job.py` (job model), `conversion.py` (Docling), `cleanup.py` (periodic), `queue.py` (Redis workers)
- SDK uses resource namespaces: `client.collections.list()`, `client.documents.upload()`, etc.

## Documentation

**Always update the docs site when making any code change.** This includes adding, updating, or removing features, endpoints, models, config options, SDK methods, or CLI flags. The docs live in `website/content/docs/` as `.mdx` files.

Pages to keep in sync:

- `api-reference/` — endpoint signatures, request/response schemas, error codes
- `concepts/` — feature explanations, examples, and curl snippets
- `sdks/typescript.mdx` — SDK method signatures and usage
- `getting-started/configuration.mdx` — environment variables and TOML options
- `deployment/` — Docker Compose snippets and production settings
- `comparison.mdx` — if a new feature is a differentiator vs competitors

If a feature is removed, remove it from the docs too. Never leave stale references.

## Development

```bash
./dev.sh            # starts infra + backend
./dev.sh --website  # docs site only
pnpm dev:app        # admin UI on localhost:3000
```

- admin UI: http://localhost:3000 (first run → `/setup` to create admin)
- Backend API: http://localhost:4000 (Swagger docs at /docs)
- Postgres: localhost:5432
- Redis: localhost:6379
- Qdrant: localhost:6333

## MCP server

The `rag-computer-mcp` entry point (`api/rag_computer/mcp_server.py`) wraps the REST
API as MCP tools for Claude Desktop / Cursor / etc. It's an HTTP client,
not an in-process bolt-on — auth is via `RAG_COMPUTER_API_KEY`. When adding or
renaming an API endpoint that retrieval clients care about, update the
matching tool in `mcp_server.py` and the docs at
`website/content/docs/sdks/mcp.mdx`.

## Auth model

Auth is admin-account + session cookie (admin UI) or minted API keys
(`ragc_sk_...`, external clients). First admin is created via the admin UI's
`/setup` page; subsequent admins via `/users`; API keys via `/api-keys`. There
is no shared-secret env var — do not introduce one.
