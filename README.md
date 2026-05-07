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
- **Generated chat** — backend-grounded chat with streaming, citations, and persisted conversations
- **Batch operations** — bulk upload, delete, status checks, and queries
- **Google Drive connector** — OAuth, in-app Drive browsing, and manual/scheduled resync
- **Status polling** — REST endpoints for document and batch processing status
- **Auth, audit, scopes** — admin accounts, session cookies, scoped `bigrag_sk_…` API keys, and full audit/access logs
- **Metadata controls** — per-collection metadata schemas, file validation, and content-hash deduplication at ingest
- **Retrieval evaluation runner** — ship recall@k / MRR / nDCG regressions against a golden set
- **Analytics** — per-collection query analytics and platform-wide stats
- **Webhooks** — HMAC-signed delivery, retries, circuit breaker, admin replay
- **Encrypted sensitive caches at rest** — provider API keys, webhook secrets, embedding-cache rows, and Redis cache payloads sealed with Fernet (`BIGRAG_MASTER_KEY`)
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
    API --> Chat[Chat]
    API --> Webhooks[Webhooks]

    Documents -->|store files| Storage[(Storage<br/>Local disk)]
    Documents -->|sync source files| Drive[Google Drive<br/>OAuth + in-app browser]
    Documents -->|enqueue| Redis[(Redis<br/>Job queue + event bus)]
    Redis -->|process| Worker[Ingestion worker]

    Worker -->|parse| Docling[Docling<br/>PDF, DOCX, HTML, Images]
    Worker -->|embed| Embedding[Embedding provider<br/>OpenAI / compatible / Cohere / Voyage]
    Worker -->|store vectors| Qdrant[(Qdrant<br/>Vector DB)]

    Query -->|search| Qdrant
    Query -->|embed query| Embedding
    Query -->|rerank| Reranker[Cohere Rerank]
    Chat -->|retrieve context| Query
    Chat -->|generate answer| LLM[Chat provider<br/>OpenAI / compatible]

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
| `GET` | `/v1/auth/whoami` | Current principal, auth method, scopes, and collection pin |
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
| `POST` | `/v1/collections/{name}/documents/batch/upload` | Batch upload (up to 100) |
| `POST` | `/v1/collections/{name}/documents/batch/status` | Batch status check |
| `POST` | `/v1/collections/{name}/documents/batch/get` | Batch get documents |
| `POST` | `/v1/collections/{name}/documents/batch/delete` | Batch delete |
| `GET` | `/v1/documents/{id}` | Cross-collection document lookup |
| `GET` | `/v1/documents/{id}/chunks` | Cross-collection chunks lookup |
| **Connectors** | | |
| `GET`/`PUT` | `/v1/admin/connectors/google` | Configure Google OAuth |
| `GET` | `/v1/connectors/google/account` | Current Google account status |
| `GET` | `/v1/connectors/google/oauth/start` | Redirect into Google OAuth |
| `GET` | `/v1/connectors/google/oauth/start-url` | Get Google OAuth redirect URL |
| `GET` | `/v1/connectors/google/oauth/callback` | Google OAuth callback |
| `POST` | `/v1/connectors/google/disconnect` | Disconnect the current Google account |
| `GET` | `/v1/connectors/google/files` | Browse Drive files and folders |
| `GET`/`POST` | `/v1/connectors/google/sources` | List or create Drive sources |
| `PATCH`/`DELETE` | `/v1/connectors/google/sources/{id}` | Update or remove a Drive source |
| `POST` | `/v1/connectors/google/sources/{id}/sync` | Manual Drive resync |
| `GET` | `/v1/connectors/google/sync-jobs` | Google Drive sync job history |
| **Chat** | | |
| `GET`/`POST` | `/v1/chat` | List conversations or create a chat turn |
| `GET`/`PATCH`/`DELETE` | `/v1/chat/{conversation_id}` | Read, rename, or delete a conversation |
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
| `PATCH`/`DELETE` | `/v1/admin/users/{id}` | Update or delete an admin/member account |
| `GET`/`POST` | `/v1/admin/api-keys` | Mint `bigrag_sk_…` API keys with scopes |
| `PATCH`/`DELETE` | `/v1/admin/api-keys/{id}` | Update, disable, or delete an API key |
| `GET` | `/v1/admin/audit` | Audit log |
| `GET` | `/v1/admin/access/overview` | Access-log rollup |
| `GET` | `/v1/admin/access/logs` | RAG access logs |
| `GET`/`POST` | `/v1/admin/embedding-presets` | Saved embedding provider configs |
| `PATCH`/`DELETE` | `/v1/admin/embedding-presets/{id}` | Update or delete an embedding preset |
| `GET`/`POST` | `/v1/admin/mcp-servers` | Manage MCP server credentials |
| `PATCH`/`DELETE` | `/v1/admin/mcp-servers/{id}` | Update or delete an MCP server |
| `POST` | `/v1/admin/mcp-servers/{id}/rotate` | Rotate an MCP server credential |
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

// Poll processing status
let current = doc;
while (current.status === "pending" || current.status === "processing") {
  await new Promise((resolve) => setTimeout(resolve, 2000));
  current = await client.documents.get("docs", doc.id);
  console.log(current.progress?.message ?? current.status, current.progress?.progress ?? 0);
}

// Query
const { results } = await client.queries.query("docs", { query: "What is RAG?" });
```

### Python

```bash
pip install bigrag==2026.5.7
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
bigrag = "2026.5.7"
```

```rust
use bigrag::BigRag;

let client = BigRag::new("http://localhost:4000", "your-key");
let result = client.queries().query("docs", bigrag::types::QueryBody {
    query: "What is RAG?".into(),
    top_k: Some(10),
    ..Default::default()
}).await?;
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

Most settings use the `BIGRAG_` prefix as environment variables, or configure via `bigrag.toml`.
Backend logging is always enabled at debug level with text output and does not use logging env vars.

| Variable | Description | Default |
|----------|-------------|---------|
| `BIGRAG_PORT` | Server port | `4000` |
| `BIGRAG_HOST` | Bind address | `127.0.0.1` |
| `BIGRAG_WORKERS` | API worker processes | `1` |
| `BIGRAG_CORS_ORIGINS` | JSON array of allowed browser origins | `[]` |
| `BIGRAG_DATABASE_URL` | Postgres URL (`postgres:5432` inside docker-compose, `localhost:5432` for bare-metal dev) | `postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable` |
| `BIGRAG_DB_POOL_MIN` | Min Postgres pool size | `5` |
| `BIGRAG_DB_POOL_MAX` | Max Postgres pool size | `50` |
| `BIGRAG_MIGRATION_TIMEOUT_SECONDS` | Startup migration check timeout (`0` disables the timeout) | `60` |
| `BIGRAG_QDRANT_URL` | Qdrant URL | `http://localhost:6333` |
| `BIGRAG_QDRANT_API_KEY` | Optional Qdrant Cloud/API key | — |
| `BIGRAG_QDRANT_CONNECT_TIMEOUT_SECONDS` | Qdrant startup connection timeout (`0` disables the timeout) | `10` |
| `BIGRAG_QDRANT_REQUIRED` | Fail API startup if Qdrant cannot be reached | `false` |
| `BIGRAG_QDRANT_SEARCH_EF` | Optional Qdrant HNSW search recall/latency tuning | — |
| `BIGRAG_REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `BIGRAG_ENV` | `dev` or `prod` (prod enables startup safety checks) | `dev` |
| `BIGRAG_TRUSTED_PROXIES` | JSON array of trusted proxy CIDRs used to honor `X-Forwarded-For` for audit and access logs | `[]` |
| `BIGRAG_SESSION_EXPIRY_HOURS` | Session cookie lifetime | `168` |
| `BIGRAG_SESSION_COOKIE_NAME` | Session cookie name | `bigrag_session` |
| `BIGRAG_SESSION_COOKIE_SECURE` | HTTPS-only session cookies | `false` |
| `BIGRAG_SESSION_COOKIE_SAMESITE` | Session cookie SameSite policy | `lax` |
| `BIGRAG_SESSION_COOKIE_DOMAIN` | Optional session cookie domain | — |
| `BIGRAG_AUTH_RATE_LIMIT_WINDOW_SECONDS` | Login/setup rate-limit window | `60` |
| `BIGRAG_AUTH_LOGIN_EMAIL_RATE_LIMIT` | Login attempts per email per window | `5` |
| `BIGRAG_AUTH_LOGIN_IP_RATE_LIMIT` | Login attempts per IP per window | `50` |
| `BIGRAG_AUTH_SETUP_IP_RATE_LIMIT` | First-admin setup attempts per IP per window | `10` |
| `BIGRAG_AUTH_PRINCIPAL_CACHE_TTL` | Principal cache TTL in seconds | `60` |

`./dev.sh` and the default Docker Compose setup allow the local admin UI origin
`http://localhost:3000`. For production, set `BIGRAG_CORS_ORIGINS` to the exact
admin UI origin. Cross-site admin UI deployments also need
`BIGRAG_SESSION_COOKIE_SECURE=true` and usually
`BIGRAG_SESSION_COOKIE_SAMESITE=none`.
| `BIGRAG_EMBEDDING_API_KEY` | Default embedding API key | — |
| `BIGRAG_EMBEDDING_PROVIDER` | Default embedding provider | `openai` |
| `BIGRAG_EMBEDDING_MODEL` | Default embedding model | `text-embedding-3-small` |
| `BIGRAG_EMBEDDING_DIMENSION` | Default embedding vector dimension | `1536` |
| `BIGRAG_EMBEDDING_BASE_URL` | Base URL for OpenAI-compatible embedding endpoints | — |
| `BIGRAG_EMBEDDING_CONCURRENCY` | Max concurrent embedding requests | `8` |
| `BIGRAG_ALLOWED_EMBEDDING_BASE_URLS` | JSON allow-list for embedding base URLs | `[]` |
| `BIGRAG_ALLOW_PRIVATE_EMBEDDING_BASE_URLS` | Allow private-network embedding endpoints | `false` |
| `BIGRAG_CHAT_PROVIDER` | Chat provider | `openai` |
| `BIGRAG_CHAT_MODEL` | Default chat model | `gpt-4o-mini` |
| `BIGRAG_CHAT_BASE_URL` | Base URL for OpenAI-compatible chat endpoints | — |
| `BIGRAG_CHAT_TEMPERATURE` | Default chat temperature | `0.2` |
| `BIGRAG_CHAT_MAX_HISTORY_MESSAGES` | Max conversation history messages used for context | `12` |
| `BIGRAG_CHAT_MAX_CONTEXT_CHARS` | Max retrieved-context characters per chat call | `120000` |
| `BIGRAG_ALLOWED_CHAT_BASE_URLS` | JSON allow-list for chat base URLs | `[]` |
| `BIGRAG_ALLOW_PRIVATE_CHAT_BASE_URLS` | Allow private-network chat endpoints | `false` |
| `BIGRAG_MASTER_KEY` | Fernet key that encrypts provider credentials, embedding cache rows, and Redis cache payloads (required in `prod`) | — |
| `BIGRAG_MASTER_KEY_PREVIOUS` | JSON array of old Fernet keys for staged rotation | `[]` |
| `BIGRAG_UPLOAD_DIR` | Local upload directory | `./data/uploads` |
| `BIGRAG_INGESTION_WORKERS` | Background workers | `4` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max single-file upload size | `64` |
| `BIGRAG_MAX_BATCH_UPLOAD_SIZE_MB` | Max total batch-upload size | `128` |
| `BIGRAG_INGESTION_BATCH_SIZE` | Vectors per embedding batch | `128` |
| `BIGRAG_CONVERSION_TIMEOUT` | Docling conversion timeout in seconds | `300` |
| `BIGRAG_CONVERSION_PDF_OCR_ENABLED` | Enable OCR for scanned PDFs | `true` |
| `BIGRAG_QUEUE_MAX_DEPTH` | Max pending jobs in the ingestion queue | `10000` |
| `BIGRAG_COLLECTION_CACHE_TTL` | Collection metadata cache TTL in seconds | `30` |
| `BIGRAG_QUERY_EMBEDDING_CACHE_TTL` | Query embedding cache TTL in seconds | `300` |
| `BIGRAG_QUERY_RESULT_CACHE_TTL` | Exact query-result cache TTL in seconds | `30` |
| `BIGRAG_EMBEDDING_CACHE_MODE` | Persistent chunk embedding cache mode (`encrypted` or `disabled`) | `encrypted` |
| `BIGRAG_EMBEDDING_CACHE_RETENTION_DAYS` | Days to keep persistent embedding-cache rows after last use | `30` |
| `BIGRAG_WEBHOOK_DELIVERY_TIMEOUT` | Webhook HTTP timeout in seconds | `10` |
| `BIGRAG_WEBHOOK_RETRY_DELAYS` | JSON array of webhook retry delays in seconds | `[10,30,90]` |
| `BIGRAG_WEBHOOK_MAX_COUNT` | Max configured webhooks | `50` |
| `BIGRAG_ALLOW_LOCAL_WEBHOOKS` | Allow webhook URLs on private/local networks | `false` |

## Supported Formats

PDF, DOCX, PPTX, XLSX, HTML, Markdown, CSV, TSV, XML, JSON, PNG, JPG, TIFF, BMP, GIF — text PDFs are extracted directly, while scanned PDFs and other rich formats are powered by [Docling](https://github.com/DS4SD/docling). Scanned-PDF OCR is enabled by default.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Sponsor

If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).

## License

[MIT](LICENSE)
