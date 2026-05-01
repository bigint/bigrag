# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Qdrant vector DB)
- `sdks/typescript/` — TypeScript SDK (`@bigrag/client`)
- `app/` — Studio admin UI (Next.js 16 + Tailwind v4 + Base UI, `@bigrag/app`)
- `website/` — Documentation site (Next.js + Fumadocs, content in `website/content/docs/`)

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

### No comments

Don't write comments or docstrings in code under `api/bigrag/`, `sdks/typescript/src/`, `app/`, or `website/`. This includes `#`, `//`, `/* */`, `/** */` JSDoc, and Python `"""docstrings"""`. The diff and well-named identifiers should speak for themselves; surprising invariants belong in commit messages or PR descriptions, not in the code. The only allowed exceptions are functional directives — shebangs, `# noqa`, `# type: ignore`, `# ruff:`, `// @ts-…`, `// biome-ignore`, `// eslint-…`, and similar tool pragmas. If you find yourself wanting to explain code, rename or restructure it instead.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, qdrant-client, docling, openai, cohere, cryptography (Fernet for at-rest encryption of provider secrets)
- **Vector DB**: Qdrant (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: OpenAI and Cohere

## Package Management

- **Python backend**: `uv` (lockfile at `api/uv.lock`)
- **TypeScript SDK + Website**: `pnpm` workspaces (root `pnpm-workspace.yaml`)

## Linting

- **Python**: `ruff` (config in `api/pyproject.toml`)
- **TypeScript/JS**: `biome` (config in `biome.jsonc`)

**Always run lint + format before committing.** Either let the pre-commit hook run them, or invoke them manually — never commit unformatted code:

```bash
# Python (api/)
uv run --project api ruff check --fix .
uv run --project api ruff format .

# TS / JS / JSON / CSS (everything else)
pnpm exec biome check --write .
```

### Pre-commit hook

The repo ships a `.pre-commit-config.yaml` that runs `ruff check`, `ruff format`, and `biome check` on staged files. Install it once per clone:

```bash
uv tool install pre-commit   # or: brew install pre-commit
pre-commit install
```

After that, every `git commit` runs the same checks CI runs (`.github/workflows/ci.yml`). If a hook auto-fixes a file, the commit aborts — re-stage and commit again.

## Architecture Notes

- Backend uses FastAPI dependency injection via `bigrag/deps.py` and `app.state`
- Database layer lives in `bigrag/db/`: `engine.py` (async engine), `session.py`
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
pnpm dev:app        # Studio admin UI on localhost:3000
```

- Studio UI: http://localhost:3000 (first run → `/setup` to create admin)
- Backend API: http://localhost:4000 (Swagger docs at /docs)
- Postgres: localhost:5432
- Redis: localhost:6379
- Qdrant: localhost:6333

## MCP server

The `bigrag-mcp` entry point (`api/bigrag/mcp_server.py`) wraps the REST
API as MCP tools for Claude Desktop / Cursor / etc. It's an HTTP client,
not an in-process bolt-on — auth is via `BIGRAG_API_KEY`. When adding or
renaming an API endpoint that retrieval clients care about, update the
matching tool in `mcp_server.py` and the docs at
`website/content/docs/sdks/mcp.mdx`.

## Auth model

Auth is admin-account + session cookie (Studio UI) or minted API keys
(`bigrag_sk_...`, external clients). First admin is created via the Studio's
`/setup` page; subsequent admins via `/users`; API keys via `/api-keys`. There
is no shared-secret env var — do not introduce one.

