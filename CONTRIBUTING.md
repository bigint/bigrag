# Contributing to bigRAG

Thank you for your interest in contributing to bigRAG. This guide will help you get started.

## Getting Started

### Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** with [pnpm](https://pnpm.io/) (via corepack)
- **Docker** and **Docker Compose** — for Postgres, Redis, Qdrant

### Development Setup

```bash
# Clone the repository
git clone https://github.com/bigint/bigrag.git
cd bigrag

# Start everything (backend + website + infrastructure)
./dev.sh

# Or start only specific services
./dev.sh --backend     # Docker infra + Python API
./dev.sh --website     # Docs site only
./dev.sh --infra       # Docker services only
./dev.sh --no-install  # Skip dependency installation (faster restart)
```

Or manually:

```bash
# Start infrastructure
docker compose up postgres redis qdrant -d

# Set up the Python backend
cd api
uv sync
uv run python -m bigrag.main
```

### Project Structure

```
bigrag/
├── api/                   # Python/FastAPI backend
│   ├── bigrag/
│   │   ├── main.py        # App factory + lifespan
│   │   ├── deps.py        # FastAPI dependency injection
│   │   ├── config.py      # Settings
│   │   ├── db/            # SQLAlchemy engine, session, ORM models, bootstrap
│   │   ├── alembic/       # Schema migrations
│   │   ├── models/        # Pydantic request/response models
│   │   ├── services/      # Business logic (embedding, ingestion, retrieval, webhooks)
│   │   ├── routers/       # API route handlers
│   │   └── middleware/    # Auth middleware
│   ├── alembic/
│   └── pyproject.toml
├── sdks/typescript/       # TypeScript SDK (@bigrag/client)
├── website/               # Docs site (Next.js + Fumadocs)
├── docker-compose.yml     # Full stack (Postgres, Redis, Qdrant, API)
├── biome.jsonc            # Biome linting config for TypeScript
├── pnpm-workspace.yaml    # pnpm workspace config
├── dev.sh                 # One-command dev setup
└── bigrag.toml            # Backend configuration
```

## Making Changes

### Branching

- Create a feature branch from `main`: `git checkout -b feat/my-feature`
- Use conventional commit prefixes: `feat/`, `fix/`, `refactor/`, `docs/`

### Coding Standards

- **Python**: Run `ruff check . && ruff format .` before committing
- **TypeScript**: Run `pnpm lint` from the root (uses Biome)
- **Type hints**: Use type annotations on all public functions

### Verifying Changes

```bash
# Website build check
pnpm --filter @bigrag/docs build

# SDK and app build checks
pnpm --filter @bigrag/client build
pnpm --filter @bigrag/app build

# Lint everything
pnpm lint          # TypeScript (Biome)
cd api && uv run ruff check . && uv run ruff format --check .  # Python
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hybrid search fusion scoring
fix: correct chunking overlap logic
refactor: simplify embedding model registry
docs: update API reference for query endpoint
chore: update ingestion pipeline fixtures
```

### Release Versioning

bigRAG release artifacts use [CalVer](https://calver.org/) with the `YYYY.M.D` scheme, without zero-padding month or day so npm, Cargo, and Python package versions stay compatible. A release on April 30, 2026 is `2026.4.30`.

When cutting a release, keep the API package, SDK packages, admin UI/docs package metadata, SDK user-agent constants, Docker image tags, and docs examples on the same CalVer version.

## Pull Request Process

1. **Open an issue first** for significant changes to discuss the approach
2. **Create a branch** from `main` with a descriptive name
3. **Make your changes** following the coding standards above
4. **Run the relevant lint, typecheck, build, and runtime smoke checks** locally
5. **Push your branch** and open a pull request against `main`
6. **Address review feedback** promptly

### PR Requirements

- All CI checks must pass (lint, biome, sdk-typecheck, website-build, app-build)
- At least one maintainer approval
- No merge conflicts with `main`

## Reporting Bugs

Open an issue with:

- bigRAG version and how you installed it (Docker, pip, source)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (run `python -m bigrag.main --log-level debug` for detailed output)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
