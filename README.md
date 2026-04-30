# bigRAG

Open-source, self-hostable RAG platform. Upload documents, auto-chunk, embed, and search — all behind a simple REST API.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- **Document ingestion** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **S3 bucket ingestion** — ingest from S3 or any S3-compatible service (MinIO, R2, Spaces, etc.), including public buckets
- **Embedding providers** — OpenAI, Cohere, and Voyage
- **Embedding presets** — save named provider/model configs once, reuse across collections
- **Vector search** — semantic, keyword, and hybrid search modes via [Milvus](https://milvus.io)
- **Reranking** — Cohere reranking for improved result relevance
- **Multi-collection queries** — search across collections in a single request
- **Batch operations** — bulk upload, delete, status checks, and queries
- **Real-time progress** — SSE streaming for document processing status
- **Auth, audit, scopes** — admin accounts, session cookies, `bigrag_sk_…` API keys with per-scope permissions and rate limits, full audit log
- **Metadata controls** — per-collection metadata schemas, file validation, and content-hash deduplication at ingest
- **Retrieval evaluation runner** — ship recall@k / MRR / nDCG regressions against a golden set
- **Analytics** — per-collection query analytics and platform-wide stats
- **Webhooks** — HMAC-signed delivery, retries, circuit breaker, admin replay
- **Encrypted credentials at rest** — provider API keys and webhook secrets sealed with Fernet (`BIGRAG_MASTER_KEY`)
- **Self-hostable** — single `docker compose up` to run everything
- **Clients** — [TypeScript](sdks/typescript), [Python](sdks/python), and [Rust](sdks/rust) SDKs plus an [MCP server](#mcp-server) for Claude Desktop, Cursor, and any MCP-aware runtime

## Quick Start

```bash
docker compose up -d
```

This starts bigRAG API, Postgres, Redis, and Milvus. Open http://localhost:4000/docs for the interactive API docs.

```bash
# Create a collection
curl -X POST http://localhost:4000/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "embedding_api_key": "sk-..."}'

# Upload a document
curl -X POST http://localhost:4000/v1/collections/docs/documents \
  -F "file=@paper.pdf"

# Ingest from a public S3 bucket
curl -X POST http://localhost:4000/v1/collections/docs/documents/s3 \
  -H "Content-Type: application/json" \
  -d '{"bucket": "indian-supreme-court-judgments", "prefix": "judgments/2025/", "region": "ap-south-1", "no_sign_request": true}'

# Query
curl -X POST http://localhost:4000/v1/collections/docs/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main findings?"}'
```

### Development

```bash
./dev.sh  # starts Postgres, Redis, Milvus, and the API with hot reload
```

### Docker Images

```bash
docker pull yoginth/bigrag:2026.4.30
```

Release artifacts use CalVer (`YYYY.M.D`); `latest` is also published for Docker images.

## Architecture

```mermaid
graph TD
    MCP([MCP client<br/>Claude / Cursor]) -->|bigrag-mcp| API
    Studio([Studio admin UI]) -->|session cookie| API
    SDK([TS / Python / Rust SDK]) -->|bigrag_sk_… key| API
    Curl([curl / any HTTP client]) -->|bigrag_sk_… key| API

    API[bigRAG API<br/>Python / FastAPI]

    API --> Auth[Auth, scopes, audit]
    API --> Collections[Collections]
    API --> Documents[Documents]
    API --> Query[Query]
    API --> Webhooks[Webhooks]

    Documents -->|store files| Storage[(Storage<br/>Local / S3)]
    Documents -->|enqueue| Redis[(Redis<br/>Job queue + event bus)]
    Redis -->|process| Worker[Ingestion worker]

    Worker -->|parse| Docling[Docling<br/>PDF, DOCX, HTML, Images]
    Worker -->|embed| Embedding[Embedding provider<br/>OpenAI / Cohere / openai_compatible]
    Worker -->|store vectors| Milvus[(Milvus<br/>Vector DB)]

    Query -->|search| Milvus
    Query -->|embed query| Embedding
    Query -->|rerank| Reranker[Cohere Rerank]

    Auth --> Postgres
    Collections --> Postgres[(Postgres<br/>Metadata + audit + deliveries)]
    Documents --> Postgres
    Webhooks --> Postgres
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Health** | | |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (all dependencies) |
| **Auth** | | |
| `GET` | `/v1/auth/setup-status` | First-run setup status |
| `POST` | `/v1/auth/setup` | Create first admin |
| `POST` | `/v1/auth/login` | Session login |
| `POST` | `/v1/auth/logout` | Revoke current session |
| `POST` | `/v1/auth/logout-all` | Revoke all sessions for user |
| `GET` | `/v1/auth/me` | Current session |
| `POST` | `/v1/auth/password` | Change password |
| `GET`/`PUT` | `/v1/auth/preferences` | Per-user Studio UI preferences |
| **Collections** | | |
| `POST` | `/v1/collections` | Create collection |
| `GET` | `/v1/collections` | List collections |
| `GET` | `/v1/collections/{name}` | Get collection |
| `PUT` | `/v1/collections/{name}` | Update collection |
| `DELETE` | `/v1/collections/{name}` | Delete collection |
| `GET` | `/v1/collections/{name}/stats` | Collection stats |
| `POST` | `/v1/collections/{name}/reembed` | Re-embed all documents with a new model |
| `POST` | `/v1/collections/{name}/truncate` | Delete all documents, keep the collection |
| `GET` | `/v1/collections/{name}/events` | Stream collection events (SSE) |
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
| `GET` | `/v1/documents/{id}` | Cross-collection document lookup |
| `GET` | `/v1/documents/{id}/chunks` | Cross-collection chunks lookup |
| **Query** | | |
| `POST` | `/v1/collections/{name}/query` | Query collection |
| `POST` | `/v1/query` | Multi-collection query |
| `POST` | `/v1/batch/query` | Batch query |
| **Vectors** | | |
| `POST` | `/v1/collections/{name}/vectors/upsert` | Upsert raw vectors |
| `POST` | `/v1/collections/{name}/vectors/delete` | Delete vectors by ID |
| **S3 jobs** | | |
| `GET` | `/v1/collections/{name}/s3-jobs` | List S3 ingest jobs |
| `GET`/`PATCH`/`DELETE` | `/v1/collections/{name}/s3-jobs/{id}` | Inspect / update / cancel a job |
| `POST` | `/v1/collections/{name}/s3-jobs/{id}/resync` | Re-scan the bucket for a job |
| **Evaluation** | | |
| `POST` | `/v1/evaluation` | Run a golden-set eval (recall@k, MRR, nDCG) |
| **Webhooks (admin)** | | |
| `GET`/`POST` | `/v1/admin/webhooks` | List / create webhooks |
| `GET`/`PUT`/`DELETE` | `/v1/admin/webhooks/{id}` | Manage a webhook |
| `POST` | `/v1/admin/webhooks/{id}/test` | Fire a test delivery |
| `GET` | `/v1/admin/webhooks/{id}/deliveries` | Delivery history |
| `POST` | `/v1/admin/webhooks/{id}/deliveries/{did}/replay` | Replay a past delivery |
| **Admin** | | |
| `GET`/`POST` | `/v1/admin/users` | Manage admin accounts |
| `GET`/`POST` | `/v1/admin/api-keys` | Mint `bigrag_sk_…` API keys with scopes |
| `GET` | `/v1/admin/audit` | Audit log |
| `GET`/`POST` | `/v1/admin/embedding-presets` | Saved embedding provider configs |
| `GET` | `/v1/stats` | Platform stats |
| `GET` | `/v1/usage` | Usage analytics |
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

const client = new BigRAG({ apiKey: "your-key", baseUrl: "http://localhost:4000" });

// Upload a document
const doc = await client.documents.upload("docs", new File([pdf], "paper.pdf"));

// Stream processing progress
for await (const event of client.documents.streamProgress("docs", doc.id)) {
  console.log(event.step, event.progress);
}

// Query
const { results } = await client.queries.query("docs", { query: "What is RAG?" });

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

client = BigRAG(api_key="your-key", base_url="http://localhost:4000")

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

### Rust

```toml
# Cargo.toml
[dependencies]
bigrag = "2026.4.30"
```

```rust
use bigrag::BigRAG;

let client = BigRAG::new("http://localhost:4000").with_api_key("your-key");
let result = client.query("docs", "What is RAG?").top_k(10).send().await?;
```

## MCP server

Expose bigRAG to Claude Desktop, Cursor, and any MCP-aware runtime:

```bash
BIGRAG_URL=https://bigrag.example.com \
BIGRAG_API_KEY=bigrag_sk_... \
bigrag-mcp
```

Drop this into `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bigrag": {
      "command": "bigrag-mcp",
      "env": {
        "BIGRAG_URL": "https://bigrag.example.com",
        "BIGRAG_API_KEY": "bigrag_sk_..."
      }
    }
  }
}
```

Full-workspace keys expose 8 tools — `list_collections`, `get_collection`, `get_collection_stats`, `query`, `multi_collection_query`, `list_documents`, `get_document`, `get_document_chunks`. Collection-pinned keys see 6 (no `list_collections` or `multi_collection_query`). See [docs/sdks/mcp](website/content/docs/sdks/mcp.mdx) for details.

## Configuration

All settings use the `BIGRAG_` prefix as environment variables, or configure via `bigrag.toml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_PORT` | Server port | `4000` |
| `BIGRAG_DATABASE_URL` | Postgres URL (`postgres:5432` inside docker-compose, `localhost:5432` for bare-metal dev) | `postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable` |
| `BIGRAG_MILVUS_URI` | Milvus URI | `http://localhost:19530` |
| `BIGRAG_REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `BIGRAG_ENV` | `dev` or `prod` (prod enables startup safety checks) | `dev` |
| `BIGRAG_TRUSTED_PROXIES` | JSON array of trusted proxy CIDRs used to honor `X-Forwarded-For` for audit and IP rate limits | `[]` |
| `BIGRAG_SESSION_COOKIE_SECURE` | HTTPS-only session cookies | `false` |
| `BIGRAG_EMBEDDING_API_KEY` | Default embedding API key | — |
| `BIGRAG_MASTER_KEY` | Fernet key that encrypts provider credentials at rest (required in `prod`) | — |
| `BIGRAG_STORAGE_BACKEND` | `local` or `s3` for document blob storage | `local` |
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
