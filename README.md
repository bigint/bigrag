# bigRAG

Open-source, self-hostable RAG platform. Upload documents, auto-chunk, embed, and search — all behind a simple REST API.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Features

- **Document ingestion** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **Embedding providers** — OpenAI, OpenAI-compatible gateways, Cohere, and Voyage
- **Embedding presets** — save named provider/model configs once, reuse across collections
- **Vector search** — semantic, keyword, and hybrid search modes via [Qdrant](https://qdrant.io)
- **Reranking** — Cohere reranking for improved result relevance
- **Multi-collection queries** — search across collections in a single request
- **Batch operations** — bulk upload, delete, status checks, and queries
- **Real-time progress** — SSE streaming for document processing status
- **Auth, audit, scopes** — admin accounts, session cookies, scoped `bigrag_sk_…` API keys, and full audit/access logs
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

This starts bigRAG API, Postgres, Redis, and Qdrant. Open http://localhost:4000/docs for the interactive API docs.

```bash
# Create a collection
curl -X POST http://localhost:4000/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "embedding_api_key": "sk-..."}'

# Upload a document
curl -X POST http://localhost:4000/v1/collections/docs/documents \
  -F "file=@paper.pdf"

# Query
curl -X POST http://localhost:4000/v1/collections/docs/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main findings?"}'
```

### Development

```bash
./dev.sh  # starts Postgres, Redis, Qdrant, and the API with hot reload
```

### Docker Images

```bash
docker pull yoginth/bigrag:2026.4.30
```

Release artifacts use CalVer (`YYYY.M.D`). Docker also publishes `latest`; the
Python SDK publishes dated PyPI releases.

## Architecture

```mermaid
graph TD
    MCP([MCP client<br/>Claude / Cursor]) -->|bigrag-mcp| API
    AdminUI([Admin UI]) -->|session cookie| API
    SDK([TS / Python / Rust SDK]) -->|bigrag_sk_… key| API
    Curl([curl / any HTTP client]) -->|bigrag_sk_… key| API

    API[bigRAG API<br/>Python / FastAPI]

    API --> Auth[Auth, scopes, audit]
    API --> Collections[Collections]
    API --> Documents[Documents]
    API --> Query[Query]
    API --> Webhooks[Webhooks]

    Documents -->|store files| Storage[(Storage<br/>Local disk)]
    Documents -->|enqueue| Redis[(Redis<br/>Job queue + event bus)]
    Redis -->|process| Worker[Ingestion worker]

    Worker -->|parse| Docling[Docling<br/>PDF, DOCX, HTML, Images]
    Worker -->|embed| Embedding[Embedding provider<br/>OpenAI / compatible / Cohere / Voyage]
    Worker -->|store vectors| Qdrant[(Qdrant<br/>Vector DB)]

    Query -->|search| Qdrant
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
| `GET`/`PUT` | `/v1/auth/preferences` | Per-user admin UI preferences |
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
| voyage | `voyage-3-large` | 1024 |
| voyage | `voyage-3.5` | 1024 |
| voyage | `voyage-3.5-lite` | 1024 |
| voyage | `voyage-code-3` | 1024 |
| voyage | `voyage-finance-2` | 1024 |
| voyage | `voyage-law-2` | 1024 |
| openai_compatible | custom model at `embedding_base_url` | custom |

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
```

### Python

```bash
pip install bigrag==2026.5.1
```

```python
from bigrag import BigRAG

client = BigRAG(api_key="your-key", base_url="http://localhost:4000")

# Upload a document
doc = await client.documents.upload("docs", "/path/to/paper.pdf")

# Query
result = await client.queries.query("docs", {"query": "What is RAG?"})
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
| `BIGRAG_WORKERS` | API worker processes | `1` |
| `BIGRAG_DATABASE_URL` | Postgres URL (`postgres:5432` inside docker-compose, `localhost:5432` for bare-metal dev) | `postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable` |
| `BIGRAG_MIGRATION_TIMEOUT_SECONDS` | Startup migration check timeout (`0` disables the timeout) | `60` |
| `BIGRAG_QDRANT_URL` | Qdrant URL | `http://localhost:6333` |
| `BIGRAG_QDRANT_API_KEY` | Optional Qdrant Cloud/API key | — |
| `BIGRAG_QDRANT_CONNECT_TIMEOUT_SECONDS` | Qdrant startup connection timeout (`0` disables the timeout) | `10` |
| `BIGRAG_QDRANT_REQUIRED` | Fail API startup if Qdrant cannot be reached | `false` |
| `BIGRAG_QDRANT_SEARCH_EF` | Optional Qdrant HNSW search recall/latency tuning | — |
| `BIGRAG_REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `BIGRAG_ENV` | `dev` or `prod` (prod enables startup safety checks) | `dev` |
| `BIGRAG_TRUSTED_PROXIES` | JSON array of trusted proxy CIDRs used to honor `X-Forwarded-For` for audit and access logs | `[]` |
| `BIGRAG_SESSION_COOKIE_SECURE` | HTTPS-only session cookies | `false` |
| `BIGRAG_EMBEDDING_API_KEY` | Default embedding API key | — |
| `BIGRAG_EMBEDDING_BASE_URL` | Base URL for OpenAI-compatible embedding endpoints | — |
| `BIGRAG_MASTER_KEY` | Fernet key that encrypts provider credentials at rest (required in `prod`) | — |
| `BIGRAG_UPLOAD_DIR` | Local upload directory | `./data/uploads` |
| `BIGRAG_INGESTION_WORKERS` | Background workers | `4` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload size | `1024` |

## Supported Formats

PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, TSV, XML, JSON, PNG, JPG, TIFF, BMP, GIF — text PDFs are extracted directly, while other rich formats are powered by [Docling](https://github.com/DS4SD/docling). Scanned-PDF OCR is available by setting `BIGRAG_CONVERSION_PDF_OCR_ENABLED=true`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Sponsor

If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).

## License

[MIT](LICENSE)
