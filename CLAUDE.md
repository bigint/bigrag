# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Milvus vector DB)
- `sdks/typescript/` — TypeScript SDK (`@bigrag/client`)
- `app/` — Studio admin UI (Next.js 16 + Tailwind v4 + Base UI, `@bigrag/app`)
- `website/` — Documentation site (Next.js + Fumadocs, content in `website/content/docs/`)

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2 (async) + asyncpg, Alembic, pymilvus, docling, openai, cohere
- **Vector DB**: Milvus (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: OpenAI and Cohere

## Package Management

- **Python backend**: `uv` (lockfile at `api/uv.lock`)
- **TypeScript SDK + Website**: `pnpm` workspaces (root `pnpm-workspace.yaml`)

## Linting

- **Python**: `ruff` (config in `api/pyproject.toml`)
- **TypeScript/JS**: `biome` (config in `biome.jsonc`)

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
pnpm dev:app        # Studio admin UI on localhost:3100
```

- Studio UI: http://localhost:3100 (first run → `/setup` to create admin)
- Backend API: http://localhost:6100 (Swagger docs at /docs)
- Postgres: localhost:5433
- Redis: localhost:6380
- Milvus: localhost:19530

## Auth model

bigRAG has no `BIGRAG_API_SECRET` env var. Auth is admin-account + session cookie
(Studio UI) or minted API keys (`bigrag_sk_...`, external clients). First admin
is created via the Studio's `/setup` page; subsequent admins via `/users`; API
keys via `/api-keys`.

## E2E Tests

After any significant API change (new endpoints, modified request/response shapes, new features, bug fixes), **run and update the E2E tests**.

```bash
cd e2e && uv run --with httpx python run.py
```

- Tests live in `e2e/tests/` — one file per feature area
- Config is in `e2e/.env` (gitignored) — copy from `e2e/.env.example`
- Tests hit the live server at `BIGRAG_URL` (default `localhost:6100`)
- All tests are real (no mocks) — they use actual Postgres, Redis, Milvus, and OpenAI

When adding or changing an endpoint:
1. Add test cases to the relevant `e2e/tests/test_*.py` file (or create a new one)
2. Run the full suite and fix any failures before committing
3. If a response shape changes, update both the test assertions and the SDK types
