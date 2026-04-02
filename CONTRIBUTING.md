# Contributing to bigRAG

Thank you for your interest in contributing to bigRAG. This guide will help you get started.

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Docker** and **Docker Compose** — for Postgres, Milvus, and integration tests
- **Node.js 22+** and **pnpm** — for the UI dashboard (`ui/` directory)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/bigint/bigrag.git
cd bigrag

# Start everything
./dev.sh
```

Or manually:

```bash
# Start infrastructure
docker compose up postgres milvus -d

# Set up the Python backend
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m bigrag.main

# Build the UI
cd ui && pnpm install && pnpm build
```

### Project Structure

```
bigrag/
├── api/                   # Python/FastAPI backend
│   ├── bigrag/
│   │   ├── main.py        # App entry point
│   │   ├── config.py      # Settings
│   │   ├── database.py    # Postgres pool + migrations
│   │   ├── models/        # Pydantic request/response models
│   │   ├── services/      # Business logic (auth, embedding, ingestion, retrieval)
│   │   ├── routers/       # API route handlers
│   │   └── middleware/     # Auth middleware
│   └── pyproject.toml
├── ui/                    # Next.js admin dashboard
├── sdks/                  # Client SDKs (Python, TypeScript)
├── docs/                  # Documentation
├── docker-compose.yml     # Full stack (Postgres, Milvus, API)
├── dev.sh                 # One-command dev setup
└── bigrag.toml            # Configuration
```

## Making Changes

### Branching

- Create a feature branch from `main`: `git checkout -b feat/my-feature`
- Use conventional commit prefixes: `feat/`, `fix/`, `refactor/`, `docs/`

### Coding Standards

**Python (backend):**
- **Format/Lint**: Run `ruff check . && ruff format .` before committing
- **Type hints**: Use type annotations on all public functions
- **Tests**: Add tests for new functionality in `api/tests/`

**TypeScript (UI):**
- **Format/Lint**: Run `pnpm lint` in the `ui/` directory
- **Components**: Follow existing patterns in `ui/src/components/`

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hybrid search fusion scoring
fix: correct chunking overlap logic
refactor: simplify embedding model registry
docs: update API reference for query endpoint
test: add ingestion pipeline tests
```

## Pull Request Process

1. **Open an issue first** for significant changes to discuss the approach
2. **Create a branch** from `main` with a descriptive name
3. **Make your changes** following the coding standards above
4. **Add tests** covering your changes
5. **Run the full check suite** locally:
   ```bash
   cd api && ruff check . && ruff format --check .
   cd ui && pnpm lint && pnpm build
   ```
6. **Push your branch** and open a pull request against `main`
7. **Address review feedback** promptly

### PR Requirements

- All CI checks must pass
- At least one maintainer approval
- No merge conflicts with `main`

## Reporting Bugs

Open an issue with:

- bigRAG version and how you installed it (Docker, pip, source)
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (set `BIGRAG_LOG_LEVEL=debug` for detailed output)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
