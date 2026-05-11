# Contributing to rag.computer

Thank you for your interest in contributing to rag.computer. This guide will help you get started.

## Getting Started

### Prerequisites

- **Python 3.12+** with [uv](https://docs.astral.sh/uv/)
- **Node.js 20+** with [pnpm](https://pnpm.io/) (via corepack)
- **Docker** and **Docker Compose** — for Postgres, Redis, Qdrant

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yoginth/rag-computer.git
cd rag-computer

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
uv run python -m rag_computer.main
```

### Project Structure

```
rag-computer/
├── api/                   # Python/FastAPI backend
│   ├── rag_computer/
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
├── sdks/typescript/       # TypeScript SDK (@rag.computer/client)
├── website/               # Docs site (Next.js + Fumadocs)
├── docker-compose.yml     # Full stack (Postgres, Redis, Qdrant, API)
├── biome.jsonc            # Biome linting config for TypeScript
├── pnpm-workspace.yaml    # pnpm workspace config
├── dev.sh                 # One-command dev setup
└── rag-computer.toml            # Backend configuration
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
pnpm --filter @rag.computer/docs build

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
test: add ingestion pipeline tests
```

### Release Versioning

rag.computer release artifacts use [CalVer](https://calver.org/) with the `YYYY.M.D` scheme, without zero-padding month or day so npm, Cargo, and Python package versions stay compatible. A release on April 30, 2026 is `2026.4.30`.

When cutting a release, keep the API package, SDK packages, admin UI/docs package metadata, SDK user-agent constants, Docker image tags, and docs examples on the same CalVer version.

## Pull Request Process

1. **Open an issue first** for significant changes to discuss the approach
2. **Create a branch** from `main` with a descriptive name
3. **Make your changes** following the coding standards above
4. **Add tests** covering your changes
5. **Run the full check suite** locally
6. **Push your branch** and open a pull request against `main`
7. **Address review feedback** promptly

### PR Requirements

- All CI checks must pass (lint, biome, sdk-typecheck, website-build, app-build)
- At least one maintainer approval
- No merge conflicts with `main`

## Reporting Bugs

Open an issue with:

- rag.computer version and how you installed it (Docker, pip, source)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (run `python -m rag_computer.main --log-level debug` for detailed output)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
