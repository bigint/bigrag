# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Milvus vector DB)
- `sdks/` — Client SDKs (Python, TypeScript)
- `docs/` — Documentation

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, asyncpg, pymilvus, docling, openai, cohere
- **Vector DB**: Milvus (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: OpenAI and Cohere

## Documentation

When introducing new features or changing existing APIs, update `docs/documentation.md` to reflect the changes. Keep SDK sections, API reference, and curl examples in sync with the actual codebase.

## Development

```bash
./dev.sh  # starts Postgres, Redis, Milvus, Python backend
```

- Backend API: http://localhost:6100 (Swagger docs at /docs)
- Postgres: localhost:5433
- Redis: localhost:6380
- Milvus: localhost:19530
