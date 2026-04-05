<p align="center">
  <h1 align="center">bigRAG</h1>
  <p align="center">Open-source, self-hostable RAG platform with document ingestion and vector search.</p>
  <p align="center">Powered by Docling + Milvus.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
</p>

---

## Features

- **End-to-end RAG pipeline** — upload documents, auto-chunk, embed, search
- **Any document format** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **Any embedding model** — OpenAI and Cohere
- **Milvus vector database** — production-grade vector search with hybrid capabilities
- **Self-hostable** — Docker Compose, no external dependencies
- **API secret auth** — protect your API with a shared secret
- **MIT licensed** — run it anywhere, forever free

## Quick Start

### Docker Compose

```bash
docker compose up -d
```

This starts the full stack:
- **bigRAG API** on port 6100 (with Swagger docs at `/docs`)
- **Postgres** for metadata and auth on port 5432
- **Redis** for the ingestion queue on port 6379
- **Milvus** vector database on port 19530

### Docker Images

Pre-built images are published to Docker Hub on every push to `main`:

```bash
docker pull yoginth/bigrag:latest
```

### Development

```bash
./dev.sh
```

This starts all services and opens:
- Backend API: http://localhost:6100
- API Docs: http://localhost:6100/docs

### From Source

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m bigrag.main --database-url postgres://bigrag:bigrag@localhost:5433/bigrag
```

## How It Works

```
Document Upload → Docling (parse any format) → Chunking → Embedding → Milvus
                                                                         ↑
Query → Embed → Vector Search ─────────────────────────────────────────→ │
                                                                         ↓
                                                              Results + Context
```

1. **Upload** any document (PDF, DOCX, PPTX, HTML, images, etc.)
2. **Docling** extracts structured text with layout understanding and OCR
3. Text is **chunked** with configurable size and overlap
4. Chunks are **embedded** using your chosen model
5. Embeddings are stored in **Milvus** for fast vector search
6. **Query** with natural language — your query is embedded and matched against stored chunks

## Usage Examples

### Python

```python
import httpx

client = httpx.Client(base_url="http://localhost:6100")

# Create a collection
client.post("/v1/collections", json={
    "name": "research",
    "description": "Research papers",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small"
})

# Upload a document
with open("paper.pdf", "rb") as f:
    client.post("/v1/collections/research/documents",
        files={"file": f})

# Query
results = client.post("/v1/collections/research/query", json={
    "query": "What are the main findings?",
    "top_k": 5
}).json()

for r in results["results"]:
    print(f"Score: {r['score']:.3f} — {r['text'][:100]}...")
```

### curl

```bash
# Health check
# → {"status":"ok","version":"0.x.x","postgres":true,"milvus":true,"redis":true}
curl http://localhost:6100/health

# Create collection
curl -X POST http://localhost:6100/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "description": "Documentation"}'

# Upload document
curl -X POST http://localhost:6100/v1/collections/docs/documents \
  -F "file=@manual.pdf"

# Query
curl -X POST http://localhost:6100/v1/collections/docs/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I configure logging?", "top_k": 5}'
```

## API Reference

| Method   | Endpoint                                          | Description                     |
| -------- | ------------------------------------------------- | ------------------------------- |
| `GET`    | `/health`                                         | Health check                    |
| `GET`    | `/v1/collections`                                 | List collections                |
| `POST`   | `/v1/collections`                                 | Create collection               |
| `GET`    | `/v1/collections/{name}`                          | Get collection details          |
| `DELETE` | `/v1/collections/{name}`                          | Delete collection               |
| `POST`   | `/v1/collections/{name}/documents`                | Upload document                 |
| `GET`    | `/v1/collections/{name}/documents`                | List documents                  |
| `DELETE` | `/v1/collections/{name}/documents/{id}`           | Delete document                 |
| `POST`   | `/v1/collections/{name}/documents/batch/upload`   | Batch upload documents          |
| `POST`   | `/v1/collections/{name}/documents/batch/status`   | Batch get document status       |
| `POST`   | `/v1/collections/{name}/documents/batch/delete`   | Batch delete documents          |
| `POST`   | `/v1/collections/{name}/documents/{id}/reprocess` | Reprocess document              |
| `POST`   | `/v1/collections/{name}/query`                    | Query collection                |
| `POST`   | `/v1/query`                                       | Multi-collection query          |
| `POST`   | `/v1/batch/query`                                 | Batch query                     |
| `GET`    | `/v1/collections/{name}/analytics`                | Collection analytics            |
| `POST`   | `/v1/admin/webhooks`                              | Register webhook                |
| `GET`    | `/v1/admin/webhooks`                              | List webhooks                   |
| `POST`   | `/v1/collections/{name}/vectors/upsert`           | Upsert raw vectors              |
| `POST`   | `/v1/collections/{name}/vectors/delete`           | Delete vectors by ID            |
| `GET`    | `/v1/embeddings/models`                           | List embedding models           |
| `GET`    | `/v1/stats`                                       | Platform stats                  |
Full interactive API docs available at `/docs` (Swagger) when running.

## Embedding Models

| Provider | Model                          | Dimensions | Notes                            |
| -------- | ------------------------------ | ---------- | -------------------------------- |
| openai   | text-embedding-3-small (default) | 1536     | OpenAI small model               |
| openai   | text-embedding-3-large         | 3072       | OpenAI large model               |
| cohere   | embed-english-v3.0             | 1024       | Cohere English model             |
| cohere   | embed-multilingual-v3.0        | 1024       | Cohere multilingual (100+ langs) |
| cohere   | embed-english-light-v3.0       | 384        | Cohere lightweight English       |
| cohere   | embed-multilingual-light-v3.0  | 384        | Cohere lightweight multilingual  |

Configure per collection or set defaults in `bigrag.toml`.

## Configuration

```toml
[server]
host = "0.0.0.0"
port = 6100
workers = 4

[database]
url = "postgres://bigrag:bigrag@localhost:5433/bigrag"

[milvus]
uri = "http://localhost:19530"

[redis]
url = "redis://localhost:6380/0"

[ingestion]
workers = 4
upload_dir = "./data/uploads"
max_upload_size_mb = 1024
```

### Environment Variables

All config options use the `BIGRAG_` prefix:

| Variable                    | Description                        | Default                    |
| --------------------------- | ---------------------------------- | -------------------------- |
| `BIGRAG_DATABASE_URL`       | Postgres connection URL            | `postgres://...`           |
| `BIGRAG_MILVUS_URI`        | Milvus connection URI              | `http://localhost:19530`   |
| `BIGRAG_REDIS_URL`         | Redis connection URL               | `redis://localhost:6380/0` |
| `BIGRAG_PORT`              | Server port                        | `6100`                     |
| `BIGRAG_WORKERS`           | Uvicorn workers                    | `4`                        |
| `BIGRAG_API_SECRET`        | Shared API secret (open access if unset) | —                    |
| `BIGRAG_LOG_LEVEL`         | Log level                          | `info`                     |
| `BIGRAG_MAX_UPLOAD_SIZE_MB`| Max upload file size               | `1024`                     |
| `BIGRAG_INGESTION_WORKERS` | Background processing workers      | `4`                        |
| `BIGRAG_CONVERSION_TIMEOUT`| Document conversion timeout (seconds) | `300`                   |
| `BIGRAG_QUEUE_MAX_DEPTH`   | Max ingestion queue depth          | `10000`                    |

Embedding provider, model, and API key are configured per collection via the API. See [full documentation](docs/documentation.md) for all environment variables.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                     bigRAG API                         │
│                   (Python/FastAPI)                      │
├──────────┬───────────┬──────────────┬─────────────────┤
│          │ Ingestion │   Query      │   Admin         │
│          │ Service   │   Service    │   Service       │
├──────────┴───────────┴──────────────┴─────────────────┤
│                                                        │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────────┐  │
│  │Postgres │  │  Redis  │  │ Docling  │  │ Embedding Model│  │
│  │(metadata│  │ (job    │  │(document │  │ (OpenAI,       │  │
│  │  store) │  │  queue) │  │ converter│  │  Cohere)       │  │
│  └─────────┘  └─────────┘  └──────────┘  └────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Milvus Vector DB                    │  │
│  │    (vector storage, indexing, search)            │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

## Supported Document Formats

Via Docling, bigRAG supports:
- PDF (with OCR for scanned documents)
- Microsoft Word (DOCX)
- Microsoft PowerPoint (PPTX)
- HTML
- Markdown
- AsciiDoc
- Images (PNG, JPG, TIFF — via OCR)
- And more

## Client SDKs

| Language   | Install                                    |
| ---------- | ------------------------------------------ |
| TypeScript | `pnpm add @bigrag/client`                  |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the PR process.

## Sponsor

If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).

## License

[MIT License](LICENSE) — use it anywhere, forever free.
