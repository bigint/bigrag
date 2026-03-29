<p align="center">
  <h1 align="center">bigRAG</h1>
  <p align="center">Open-source, self-hostable RAG platform with document ingestion and vector search.</p>
  <p align="center">Powered by Docling + Milvus.</p>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License"></a>
  <a href="https://github.com/bigrag-io/bigrag/actions/workflows/ci.yml"><img src="https://github.com/bigrag-io/bigrag/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

---

## Features

- **End-to-end RAG pipeline** — upload documents, auto-chunk, embed, search
- **Any document format** — PDF, DOCX, PPTX, HTML, Markdown, images, and more via [Docling](https://github.com/DS4SD/docling)
- **Any embedding model** — sentence-transformers (local), OpenAI, Ollama, or any OpenAI-compatible API
- **Milvus vector database** — production-grade vector search with hybrid capabilities
- **Admin web UI** — manage collections, upload documents, query, and administer users
- **Self-hostable** — Docker Compose, no external dependencies
- **User auth** — session-based auth with invite system, API keys, and role-based access
- **Apache 2.0** — run it anywhere, forever free

## Quick Start

### Docker Compose

```bash
docker compose up -d
```

This starts the full stack:
- **bigRAG API** on port 8080 (with Swagger docs at `/docs`)
- **Milvus** vector database on port 19530
- **Postgres** for metadata and auth on port 5432

### Development

```bash
./dev.sh
```

This starts all services and opens:
- Backend API: http://localhost:8080
- API Docs: http://localhost:8080/docs
- Admin UI: http://localhost:3000

### From Source

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m bigrag.main --database-url postgres://bigrag:bigrag@localhost:5432/bigrag
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

client = httpx.Client(base_url="http://localhost:8080")

# Create a collection
client.post("/v1/collections", json={
    "name": "research",
    "description": "Research papers",
    "embedding_model": "all-MiniLM-L6-v2"
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
curl http://localhost:8080/health

# Create collection
curl -X POST http://localhost:8080/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "docs", "description": "Documentation"}'

# Upload document
curl -X POST http://localhost:8080/v1/collections/docs/documents \
  -F "file=@manual.pdf"

# Query
curl -X POST http://localhost:8080/v1/collections/docs/query \
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
| `POST`   | `/v1/collections/{name}/documents/{id}/reprocess` | Reprocess document              |
| `POST`   | `/v1/collections/{name}/query`                    | Query collection                |
| `POST`   | `/v1/collections/{name}/vectors/upsert`           | Upsert raw vectors              |
| `POST`   | `/v1/collections/{name}/vectors/delete`           | Delete vectors by ID            |
| `GET`    | `/v1/embeddings/models`                           | List embedding models           |
| `GET`    | `/v1/metrics`                                     | Prometheus metrics              |
| `POST`   | `/v1/auth/setup`                                  | Initial admin setup             |
| `POST`   | `/v1/auth/login`                                  | Login                           |
| `POST`   | `/v1/auth/signup`                                 | Signup with invite              |
| `GET`    | `/v1/auth/me`                                     | Current user                    |

Full interactive API docs available at `/docs` (Swagger) when running.

## Embedding Models

| Provider             | Model                      | Dimensions | Notes                        |
| -------------------- | -------------------------- | ---------- | ---------------------------- |
| sentence-transformers | all-MiniLM-L6-v2 (default) | 384        | Fast, lightweight            |
| sentence-transformers | all-mpnet-base-v2          | 768        | Higher quality               |
| sentence-transformers | multilingual-e5-large      | 1024       | 100+ languages               |
| openai               | text-embedding-3-small     | 1536       | Requires API key             |
| openai               | text-embedding-3-large     | 3072       | Best quality (OpenAI)        |
| ollama               | nomic-embed-text           | 768        | Local via Ollama             |
| custom               | Any                        | Any        | OpenAI-compatible endpoint   |

Configure per collection or set defaults in `bigrag.toml`.

## Configuration

```toml
[server]
host = "0.0.0.0"
port = 8080

[database]
url = "postgres://bigrag:bigrag@localhost:5432/bigrag"

[milvus]
uri = "http://localhost:19530"

[embedding]
provider = "sentence-transformers"
model = "all-MiniLM-L6-v2"
dimension = 384

[ingestion]
chunk_size = 512
chunk_overlap = 50
upload_dir = "./data/uploads"
max_upload_size_mb = 500
```

### Environment Variables

All config options use the `BIGRAG_` prefix:

| Variable                  | Description                        | Default                  |
| ------------------------- | ---------------------------------- | ------------------------ |
| `BIGRAG_DATABASE_URL`     | Postgres connection URL            | `postgres://...`         |
| `BIGRAG_MILVUS_URI`       | Milvus connection URI              | `http://localhost:19530` |
| `BIGRAG_PORT`             | Server port                        | `8080`                   |
| `BIGRAG_MASTER_KEY`       | Admin master key                   | —                        |
| `BIGRAG_API_KEYS`         | Comma-separated API keys           | —                        |
| `BIGRAG_EMBEDDING_PROVIDER` | Default embedding provider       | `sentence-transformers`  |
| `BIGRAG_EMBEDDING_MODEL`  | Default embedding model            | `all-MiniLM-L6-v2`      |
| `BIGRAG_EMBEDDING_API_KEY`| API key for OpenAI/Cohere          | —                        |
| `BIGRAG_LOG_LEVEL`        | Log level                          | `info`                   |

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                     bigRAG API                         │
│                   (Python/FastAPI)                      │
├──────────┬───────────┬──────────────┬─────────────────┤
│  Auth    │ Ingestion │   Query      │   Admin         │
│  Service │ Service   │   Service    │   Service       │
├──────────┴───────────┴──────────────┴─────────────────┤
│                                                        │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │Postgres │  │   Docling    │  │  Embedding Model │  │
│  │(auth +  │  │ (document    │  │ (sentence-xfmr,  │  │
│  │metadata)│  │  converter)  │  │  OpenAI, Ollama) │  │
│  └─────────┘  └──────────────┘  └──────────────────┘  │
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
| Python     | `pip install bigrag`                       |
| TypeScript | `npm install @bigrag/client`               |
| Go         | `go get github.com/bigrag-io/bigrag-go`    |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, coding standards, and the PR process.

## License

[Apache License 2.0](LICENSE) — use it anywhere, forever free.
