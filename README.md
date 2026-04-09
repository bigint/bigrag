# bigRAG

Open-source, self-hostable RAG platform. Upload documents, auto-chunk, embed, and search — all behind a simple REST API.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- **Document ingestion** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **S3 bucket ingestion** — ingest from S3 or any S3-compatible service (MinIO, R2, Spaces, etc.), including public buckets
- **Embedding providers** — OpenAI and Cohere, configurable per collection
- **Vector search** — semantic, keyword, and hybrid search modes via [Milvus](https://milvus.io)
- **Reranking** — Cohere reranking for improved result relevance
- **Multi-collection queries** — search across collections in a single request
- **Batch operations** — bulk upload, delete, status checks, and queries
- **Real-time progress** — SSE streaming for document processing status
- **Analytics** — per-collection query analytics and platform-wide stats
- **Webhooks** — get notified when documents are processed
- **Self-hostable** — single `docker compose up` to run everything
- **SDKs** — [TypeScript](sdks/typescript) and [Python](sdks/python) clients

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

# Ingest from a public S3 bucket
curl -X POST http://localhost:6100/v1/collections/docs/documents/s3 \
  -H "Content-Type: application/json" \
  -d '{"bucket": "indian-supreme-court-judgments", "prefix": "judgments/2025/", "region": "ap-south-1", "no_sign_request": true}'

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
    Query -->|rerank| Reranker[Cohere Rerank]

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
| `GET` | `/v1/collections/{name}/stats` | Collection stats |
| **Documents** | | |
| `POST` | `/v1/collections/{name}/documents` | Upload document |
| `GET` | `/v1/collections/{name}/documents` | List documents |
| `GET` | `/v1/collections/{name}/documents/{id}` | Get document |
| `DELETE` | `/v1/collections/{name}/documents/{id}` | Delete document |
| `POST` | `/v1/collections/{name}/documents/{id}/reprocess` | Reprocess document |
| `GET` | `/v1/collections/{name}/documents/{id}/chunks` | Get document chunks |
| `GET` | `/v1/collections/{name}/documents/{id}/file` | Download original file |
| `GET` | `/v1/collections/{name}/documents/{id}/progress` | Stream processing progress (SSE) |
| `POST` | `/v1/collections/{name}/documents/s3` | Ingest from S3 bucket |
| `POST` | `/v1/collections/{name}/documents/batch/upload` | Batch upload (up to 100) |
| `POST` | `/v1/collections/{name}/documents/batch/status` | Batch status check |
| `POST` | `/v1/collections/{name}/documents/batch/get` | Batch get documents |
| `POST` | `/v1/collections/{name}/documents/batch/delete` | Batch delete |
| `GET` | `/v1/collections/{name}/documents/batch/progress` | Stream batch progress (SSE) |
| **Query** | | |
| `POST` | `/v1/collections/{name}/query` | Query collection |
| `POST` | `/v1/query` | Multi-collection query |
| `POST` | `/v1/batch/query` | Batch query |
| **Vectors** | | |
| `POST` | `/v1/collections/{name}/vectors/upsert` | Upsert raw vectors |
| `POST` | `/v1/collections/{name}/vectors/delete` | Delete vectors by ID |
| **Webhooks** | | |
| `POST` | `/v1/admin/webhooks` | Create webhook |
| `GET` | `/v1/admin/webhooks` | List webhooks |
| **Admin** | | |
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

## SDKs

### TypeScript

```bash
npm install @bigrag/client
```

```typescript
import { BigRAG } from "@bigrag/client";

const client = new BigRAG({ apiKey: "your-key", baseUrl: "http://localhost:6100" });

// Upload a document
const doc = await client.uploadDocument("docs", new File([pdf], "paper.pdf"));

// Stream processing progress
for await (const event of client.streamDocumentProgress("docs", doc.id)) {
  console.log(event.step, event.progress);
}

// Query
const { results } = await client.query("docs", { query: "What is RAG?" });

// Ingest from S3
await client.documents.ingestS3("docs", {
  bucket: "my-bucket",
  prefix: "reports/",
  no_sign_request: true,
});
```

### Python

```bash
pip install bigrag
```

```python
from bigrag import BigRAG

client = BigRAG(api_key="your-key", base_url="http://localhost:6100")

# Upload a document
doc = await client.documents.upload("docs", "/path/to/paper.pdf")

# Query
result = await client.queries.query("docs", {"query": "What is RAG?"})

# Ingest from S3
result = await client.documents.ingest_s3(
    "docs",
    bucket="my-bucket",
    prefix="reports/",
    no_sign_request=True,
)
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

## Supported Formats

PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, TSV, XML, JSON, PNG, JPG, TIFF, BMP, GIF — powered by [Docling](https://github.com/DS4SD/docling) with OCR support for scanned documents and images.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Sponsor

If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).

## License

[MIT](LICENSE)
