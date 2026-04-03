# Development Setup

## Prerequisites

- Python 3.12+
- Node.js 22+ and pnpm
- Docker and Docker Compose (for Postgres, Milvus)

## One-Command Start

```bash
./dev.sh
```

This starts everything: Postgres, Milvus, the Python backend, and the Next.js UI.

## Manual Setup

### 1. Start infrastructure

```bash
docker compose up postgres milvus -d
```

Wait for services to be healthy:

```bash
# Postgres
docker exec bigrag-postgres pg_isready -U bigrag

# Milvus
curl -f http://localhost:9091/healthz
```

### 2. Run the backend

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e .

BIGRAG_DATABASE_URL="postgres://bigrag:bigrag@localhost:5432/bigrag" \
BIGRAG_MILVUS_URI="http://localhost:19530" \
python -m bigrag.main
```

API: http://localhost:8080 | Swagger docs: http://localhost:8080/docs

### 3. Run the UI

```bash
cd ui
pnpm install
pnpm dev
```

Dashboard: http://localhost:3000

On first visit, the UI redirects to `/setup` to create the initial admin account. After that, users log in with email/password.

## Verify

```bash
curl http://localhost:8080/health
```

## Services

| Service  | URL                          | Notes                    |
|----------|------------------------------|--------------------------|
| API      | http://localhost:8080         | FastAPI + Swagger at /docs |
| UI       | http://localhost:3000         | Next.js admin dashboard  |
| Postgres | localhost:5432               | User: bigrag / bigrag    |
| Milvus   | localhost:19530              | Vector DB                |
