# bigRAG Platform Monorepo - Claude Instructions

## Project Structure

- `api/` — Python/FastAPI backend (Docling ingestion + Milvus vector DB)
- `sdks/typescript/` — TypeScript SDK
- `website/` — Documentation site (Next.js + Fumadocs, content in `website/content/docs/`)

## Style Guide

All coding guidelines, patterns, and conventions are documented in **[STYLEGUIDE.md](./STYLEGUIDE.md)**. Follow the rules and patterns defined there.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, asyncpg, pymilvus, docling, openai, cohere
- **Vector DB**: Milvus (via Docker)
- **Metadata DB**: PostgreSQL 17
- **Ingestion**: Docling (PDF, DOCX, PPTX, HTML, Markdown, images)
- **Embedding**: OpenAI and Cohere

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
./dev.sh  # starts Postgres, Redis, Milvus, Python backend
```

- Backend API: http://localhost:6100 (Swagger docs at /docs)
- Postgres: localhost:5433
- Redis: localhost:6380
- Milvus: localhost:19530
