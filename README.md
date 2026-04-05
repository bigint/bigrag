# bigRAG

Open-source, self-hostable RAG platform. Upload documents, auto-chunk, embed, and search — all behind a simple REST API.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- **Document ingestion** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **Embedding providers** — OpenAI and Cohere, configurable per collection
- **Vector search** — semantic, keyword, and hybrid search modes via [Milvus](https://milvus.io)
- **Batch operations** — bulk upload, delete, and status checks
- **Webhooks** — get notified when documents are processed
- **Self-hostable** — single `docker compose up` to run everything
- **TypeScript SDK** — zero-dependency client for Node.js, browsers, and edge runtimes

## Quick Start

```bash
docker compose up -d
```

This starts bigRAG API, Postgres, Redis, and Milvus. Open http://localhost:6100/docs for the interactive API docs.

```bash
# Create a collection
curl -X POST http://localhost:6100/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "embedding_api_key": "sk-..."}'

# Upload a document
curl -X POST http://localhost:6100/v1/collections/docs/documents \
  -F "file=@paper.pdf"

# Query
curl -X POST http://localhost:6100/v1/collections/docs/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main findings?"}'
```

### Development

```bash
./dev.sh  # starts Postgres, Redis, Milvus, and the API with hot reload
```

### Docker Images

```bash
docker pull yoginth/bigrag:latest
```

## Architecture

```mermaid
graph TD
    Client([Client]) -->|REST API| API[bigRAG API<br/>Python / FastAPI]

    API --> Collections[Collections]
    API --> Documents[Documents]
    API --> Query[Query]
    API --> Webhooks[Webhooks]

    Documents -->|store files| Storage[(Storage<br/>Local / S3)]
    Documents -->|enqueue| Redis[(Redis<br/>Job Queue)]
    Redis -->|process| Worker[Ingestion Worker]

    Worker -->|parse| Docling[Docling<br/>PDF, DOCX, HTML, Images]
    Worker -->|embed| Embedding[Embedding Provider<br/>OpenAI / Cohere]
    Worker -->|store vectors| Milvus[(Milvus<br/>Vector DB)]

    Query -->|search| Milvus
    Query -->|embed query| Embedding

    Collections --> Postgres[(Postgres<br/>Metadata)]
    Documents --> Postgres
    Webhooks --> Postgres
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Health** | | |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (all dependencies) |
| **Collections** | | |
| `POST` | `/v1/collections` | Create collection |
| `GET` | `/v1/collections` | List collections |
| `GET` | `/v1/collections/{name}` | Get collection |
| `PUT` | `/v1/collections/{name}` | Update collection |
| `DELETE` | `/v1/collections/{name}` | Delete collection |
| **Documents** | | |
| `POST` | `/v1/collections/{name}/documents` | Upload document |
| `GET` | `/v1/collections/{name}/documents` | List documents |
| `GET` | `/v1/collections/{name}/documents/{id}` | Get document |
| `DELETE` | `/v1/collections/{name}/documents/{id}` | Delete document |
| `POST` | `/v1/collections/{name}/documents/{id}/reprocess` | Reprocess document |
| `POST` | `/v1/collections/{name}/documents/batch/upload` | Batch upload (up to 100) |
| `POST` | `/v1/collections/{name}/documents/batch/status` | Batch status check |
| `POST` | `/v1/collections/{name}/documents/batch/delete` | Batch delete |
| **Query** | | |
| `POST` | `/v1/collections/{name}/query` | Query collection |
| `POST` | `/v1/query` | Multi-collection query |
| `POST` | `/v1/batch/query` | Batch query |
| **Vectors** | | |
| `POST` | `/v1/collections/{name}/vectors/upsert` | Upsert raw vectors |
| `POST` | `/v1/collections/{name}/vectors/delete` | Delete vectors by ID |
| **Admin** | | |
| `POST` | `/v1/admin/webhooks` | Create webhook |
| `GET` | `/v1/admin/webhooks` | List webhooks |
| `GET` | `/v1/stats` | Platform stats |
| `GET` | `/v1/embeddings/models` | List embedding models |
| `GET` | `/v1/collections/{name}/analytics` | Collection analytics |

Full interactive docs at `/docs` (Swagger UI) when running.

## Embedding Models

| Provider | Model | Dimensions |
|----------|-------|------------|
| openai | `text-embedding-3-small` (default) | 1536 |
| openai | `text-embedding-3-large` | 3072 |
| cohere | `embed-english-v3.0` | 1024 |
| cohere | `embed-multilingual-v3.0` | 1024 |
| cohere | `embed-english-light-v3.0` | 384 |
| cohere | `embed-multilingual-light-v3.0` | 384 |

## TypeScript SDK

```bash
npm install @bigrag/client
```

```typescript
import { BigRAG } from "@bigrag/client";

const client = new BigRAG({ apiKey: "your-key", baseUrl: "http://localhost:6100" });

// Create a collection
await client.createCollection({ name: "docs" });

// Upload documents
const doc = await client.uploadDocument("docs", new File([pdf], "paper.pdf"));

// Query
const { results } = await client.query("docs", { query: "What is RAG?" });

// Batch operations
await client.batchUploadDocuments("docs", [file1, file2, file3]);
await client.batchGetStatus("docs", [doc1.id, doc2.id]);
await client.batchDeleteDocuments("docs", [doc1.id]);

// Platform stats
const stats = await client.getStats();
```

## Configuration

All settings use the `BIGRAG_` prefix as environment variables, or configure via `bigrag.toml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_PORT` | Server port | `6100` |
| `BIGRAG_DATABASE_URL` | Postgres URL | `postgres://bigrag:bigrag@localhost:5433/bigrag` |
| `BIGRAG_MILVUS_URI` | Milvus URI | `http://localhost:19530` |
| `BIGRAG_REDIS_URL` | Redis URL | `redis://localhost:6380/0` |
| `BIGRAG_API_SECRET` | API auth secret (open if unset) | — |
| `BIGRAG_EMBEDDING_API_KEY` | Default embedding API key | — |
| `BIGRAG_INGESTION_WORKERS` | Background workers | `4` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload size | `1024` |

See [full documentation](docs/documentation.md) for all options.

## Supported Formats

PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, TSV, XML, JSON, PNG, JPG, TIFF, BMP, GIF — powered by [Docling](https://github.com/DS4SD/docling) with OCR support for scanned documents and images.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Sponsor

If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).

## License

[MIT](LICENSE)
