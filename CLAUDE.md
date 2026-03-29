# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Milvus vector DB)
- `ui/` — Next.js 16 admin dashboard (React 19 + TanStack Query + Tailwind 4)
- `sdks/` — Client SDKs (Python, TypeScript, Go)
- `docs/` — Documentation
- `helm/` — Kubernetes Helm chart

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, asyncpg, pymilvus, docling, sentence-transformers
- **Vector DB**: Milvus (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Frontend**: Next.js 16, React 19, TypeScript 6, Tailwind CSS 4, TanStack Query v5
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: Pluggable (sentence-transformers, OpenAI, Ollama, custom)

## Development

```bash
./dev.sh  # starts Postgres, Milvus, Python backend, Next.js UI
```

- Backend API: http://localhost:8080 (Swagger docs at /docs)
- Admin UI: http://localhost:3000
- Milvus: localhost:19530
- Postgres: localhost:5432
