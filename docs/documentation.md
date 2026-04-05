# bigRAG Documentation

Complete reference for the bigRAG open-source RAG platform — document ingestion, vector search, and retrieval-augmented generation.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Docker Compose (Recommended)](#docker-compose-recommended)
  - [From Source](#from-source)
  - [Development Mode](#development-mode)
- [Authentication](#authentication)
- [Configuration](#configuration)
  - [TOML Configuration](#toml-configuration)
  - [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
  - [Health](#health)
  - [Collections](#collections)
  - [Documents](#documents)
  - [Query & Search](#query--search)
  - [Multi-Collection Query](#multi-collection-query)
  - [Hybrid Search](#hybrid-search)
  - [Reranking](#reranking)
  - [Batch Query](#batch-query)
  - [Collection Analytics](#collection-analytics)
  - [Vectors (Direct)](#vectors-direct)
  - [Embedding Models](#embedding-models)
  - [Admin: Webhooks](#admin-webhooks)
  - [Platform Stats](#platform-stats)
- [Embedding Providers](#embedding-providers)
- [Document Ingestion Pipeline](#document-ingestion-pipeline)
  - [Supported Formats](#supported-formats)
  - [How Ingestion Works](#how-ingestion-works)
  - [Chunking Strategy](#chunking-strategy)
  - [Processing Status](#processing-status)
  - [Real-Time Progress (SSE)](#real-time-progress-sse)
- [Storage Backends](#storage-backends)
- [TypeScript SDK](#typescript-sdk)
- [curl Examples](#curl-examples)
- [Error Codes](#error-codes)
- [Rate Limiting](#rate-limiting)
- [Deployment](#deployment)
  - [Docker Compose Production](#docker-compose-production)
  - [Environment Variables for Production](#environment-variables-for-production)
- [Troubleshooting](#troubleshooting)

---

## Overview

bigRAG is an open-source, self-hostable RAG (Retrieval-Augmented Generation) platform. It provides a complete pipeline for document ingestion, chunking, embedding, and vector search — all behind a simple REST API.

**Key features:**

- **End-to-end RAG pipeline** — upload documents, auto-chunk, embed, and search in one platform
- **Any document format** — PDF, DOCX, PPTX, HTML, Markdown, images (with OCR), and more via [Docling](https://github.com/DS4SD/docling)
- **Any embedding model** — OpenAI and Cohere
- **Milvus vector database** — production-grade vector search with hybrid capabilities
- **Self-hostable** — Docker Compose, no external dependencies
- **API secret auth** — protect your API with a shared secret
- **MIT licensed** — run it anywhere, forever free

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      bigRAG API                            │
│                    (Python / FastAPI)                       │
├───────────┬────────────┬───────────────┬──────────────────┤
│           │ Ingestion  │    Query      │     Admin        │
│           │  Service   │   Service     │    Service       │
├───────────┴────────────┴───────────────┴──────────────────┤
│                                                            │
│  ┌──────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ Postgres │  │    Docling    │  │  Embedding Model  │   │
│  │(metadata)│  │  (document    │  │ (OpenAI,           │   │
│  │          │  │   converter)  │  │  Cohere)           │   │
│  └──────────┘  └───────────────┘  └───────────────────┘   │
│                                                            │
│  ┌──────────┐  ┌───────────────────────────────────────┐  │
│  │  Redis   │  │          Milvus Vector DB             │  │
│  │ (queue)  │  │   (vector storage, indexing, search)  │  │
│  └──────────┘  └───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

**Data flow:**

```
Document Upload → Docling (parse any format) → Chunking → Embedding → Milvus
                                                                        ↑
Query → Embed → Vector Search ────────────────────────────────────────→ │
                                                                        ↓
                                                             Results + Context
```

**Components:**

| Component | Purpose | Default Address |
|-----------|---------|-----------------|
| **bigRAG API** | REST API server (FastAPI) | `http://localhost:6100` |
| **PostgreSQL** | Metadata storage | `localhost:5433` |
| **Milvus** | Vector storage and search | `localhost:19530` |
| **Redis** | Ingestion job queue | `localhost:6380` |

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (recommended method)
- **Python 3.12+** (for running from source)

### Docker Compose (Recommended)

```bash
docker compose up -d
```

This starts the full stack:

- **bigRAG API** on port 6100 (Swagger docs at `/docs`)
- **Milvus** vector database on port 19530
- **Postgres** for metadata and auth on port 5432
- **Redis** for the ingestion queue on port 6379

### From Source

```bash
# 1. Start infrastructure
docker compose up postgres milvus redis -d

# 2. Install and run the backend
cd api
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m bigrag.main \
  --database-url "postgres://bigrag:bigrag@localhost:5433/bigrag" \
  --milvus-uri "http://localhost:19530"
```

### Development Mode

The easiest way to start everything for development:

```bash
./dev.sh
```

This script:

1. Kills stale processes on port 6100
2. Validates required commands (`docker`, `python3`, `curl`)
3. Starts Docker services (Postgres, Redis, Milvus) and waits for readiness
4. Creates a Python virtualenv and installs dependencies
5. Starts the backend with auto-reload
6. Gracefully stops everything on Ctrl+C

### Verify

```bash
curl http://localhost:6100/health
# → {"status": "ok", "version": "0.x.x"}
```

---

## Authentication

bigRAG uses a simple shared secret for API protection. Set the `BIGRAG_API_SECRET` environment variable to require authentication. If the variable is not set, the API is open to all requests.

When `BIGRAG_API_SECRET` is set, all requests must include the secret in the `Authorization` header:

```bash
curl http://localhost:6100/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"
```

This is a simple, stateless auth model — there are no user accounts, sessions, or API key management.

---

## Configuration

bigRAG reads configuration from a `bigrag.toml` file and/or environment variables. Environment variables take precedence over TOML values.

### TOML Configuration

Create a `bigrag.toml` file in the project root:

```toml
[server]
host = "0.0.0.0"
port = 6100
workers = 4
log_level = "info"          # debug, info, warning, error
log_format = "text"         # text, json
cors_origins = ["*"]

[database]
url = "postgres://bigrag:bigrag@localhost:5433/bigrag?sslmode=disable"
pool_min = 5
pool_max = 50

[milvus]
uri = "http://localhost:19530"

[redis]
url = "redis://localhost:6380/0"

[auth]
api_secret = ""             # Shared API secret (open access if empty)

[ingestion]
workers = 4
upload_dir = "./data/uploads"
max_upload_size_mb = 1024

[storage]
backend = "local"           # local, s3

[s3]
bucket = ""
endpoint_url = ""
region = "us-east-1"
access_key = ""
secret_key = ""
```

### Environment Variables

All settings use the `BIGRAG_` prefix. Environment variables override TOML values.

| Variable | Description | Default |
|----------|-------------|---------|
| **Server** | | |
| `BIGRAG_PORT` | Server port | `6100` |
| `BIGRAG_HOST` | Bind address | `0.0.0.0` |
| `BIGRAG_WORKERS` | Uvicorn workers | `4` |
| `BIGRAG_LOG_LEVEL` | Log level (`debug`, `info`, `warning`, `error`) | `info` |
| `BIGRAG_LOG_FORMAT` | Log format (`text`, `json`) | `text` |
| **Infrastructure** | | |
| `BIGRAG_DATABASE_URL` | Postgres connection URL | `postgres://bigrag:bigrag@localhost:5433/bigrag?sslmode=disable` |
| `BIGRAG_MILVUS_URI` | Milvus connection URI | `http://localhost:19530` |
| `BIGRAG_REDIS_URL` | Redis connection URL | `redis://localhost:6380/0` |
| **Auth** | | |
| `BIGRAG_API_SECRET` | Shared API secret (open access if unset) | — |
| **Database** | | |
| `BIGRAG_DB_POOL_MIN` | Minimum connection pool size | `5` |
| `BIGRAG_DB_POOL_MAX` | Maximum connection pool size | `50` |
| **Ingestion** | | |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload file size in MB | `1024` |
| `BIGRAG_INGESTION_WORKERS` | Background processing workers | `4` |
| `BIGRAG_INGESTION_BATCH_SIZE` | Vectors per embedding batch | `128` |
| `BIGRAG_CHUNK_SIZE` | Default chunk size (characters) | `512` |
| `BIGRAG_CHUNK_OVERLAP` | Default chunk overlap (characters) | `50` |
| **Storage** | | |
| `BIGRAG_STORAGE_BACKEND` | Storage backend (`local`, `s3`) | `local` |
| `BIGRAG_UPLOAD_DIR` | Local upload directory | `./data/uploads` |
| `BIGRAG_S3_BUCKET` | S3 bucket name | — |
| `BIGRAG_S3_ENDPOINT_URL` | S3 endpoint URL | — |
| `BIGRAG_S3_REGION` | S3 region | `us-east-1` |
| **Tuning** | | |
| `BIGRAG_EMBEDDING_CONCURRENCY` | Max concurrent embedding requests | `8` |
| `BIGRAG_MILVUS_MAX_WORKERS` | Milvus thread pool size | `32` |
| `BIGRAG_MILVUS_NPROBE` | Milvus search nprobe parameter | `32` |
| `BIGRAG_COLLECTION_CACHE_TTL` | Collection cache TTL in seconds | `30` |
| `BIGRAG_QUEUE_MAX_DEPTH` | Max ingestion queue depth | `10000` |
| `BIGRAG_CONVERSION_TIMEOUT` | Document conversion timeout (seconds) | `300` |
| `BIGRAG_WEBHOOK_DELIVERY_TIMEOUT` | Webhook HTTP timeout (seconds) | `10` |
| `BIGRAG_WEBHOOK_CACHE_TTL` | Webhook cache TTL in seconds | `60` |
| `BIGRAG_CORS_ORIGINS` | Allowed CORS origins | `["*"]` |
| `BIGRAG_SESSION_EXPIRY_HOURS` | Session expiry in hours | `168` |

Embedding provider, model, API key, chunk size, and chunk overlap are configured per collection via the API. The `CHUNK_SIZE` and `CHUNK_OVERLAP` settings above are server-level defaults used when not specified per-collection.

---

## API Reference

All API endpoints are prefixed with `/v1` (except `/health`). When `BIGRAG_API_SECRET` is set, pass the secret via the `Authorization: Bearer <secret>` header.

Base URL: `http://localhost:6100`

Interactive Swagger docs: `http://localhost:6100/docs`

### Health

#### `GET /health`

Liveness check. No authentication required. Always returns 200 if the server is running.

**Response:**

```json
{
  "status": "ok",
  "version": "0.0.2"
}
```

#### `GET /health/ready`

Readiness check. Tests connectivity to Postgres, Milvus, and Redis. No authentication required.

**Response (200):**

```json
{
  "status": "ok",
  "version": "0.0.2",
  "postgres": true,
  "milvus": true,
  "redis": true
}
```

Returns HTTP 503 with `"status": "degraded"` when any dependency is unhealthy.

---

### Collections

Collections are logical groupings of documents that share the same embedding configuration. Each collection maps to a Milvus collection for vector storage.

Base path: `/v1/collections`

#### `GET /v1/collections`

List all collections.

**Response** `200`:

```json
{
  "collections": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "research_papers",
      "description": "Academic research papers",
      "embedding_provider": "openai",
      "embedding_model": "text-embedding-3-small",
      "dimension": 1536,
      "chunk_size": 512,
      "chunk_overlap": 50,
      "document_count": 15,
      "has_api_key": false,
      "metadata": {},
      "created_at": "2026-04-01T00:00:00Z",
      "updated_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

#### `POST /v1/collections`

Create a new collection.

**Request body:**

```json
{
  "name": "research_papers",
  "description": "Academic research papers",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "dimension": 1536,
  "chunk_size": 512,
  "chunk_overlap": 50,
  "metadata": {
    "team": "research"
  }
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | 1-128 chars, must match `[a-zA-Z][a-zA-Z0-9_]*` |
| `description` | string | no | `""` | — |
| `embedding_provider` | string | no | Server default | `openai`, `cohere` |
| `embedding_model` | string | no | Server default | Model name for the provider |
| `embedding_api_key` | string | no | — | Required for `openai`, `cohere` |
| `dimension` | integer | no | Server default | Embedding vector dimension |
| `chunk_size` | integer | no | `512` | 64–10,000 |
| `chunk_overlap` | integer | no | `50` | 0–5,000 (must be < `chunk_size`) |
| `metadata` | object | no | `{}` | Arbitrary key-value pairs |

**Response** `201`: Full `CollectionResponse` object (see list response).

**Errors:**

- `400` — Invalid name format, invalid chunk config
- `409` — Collection name already exists

#### `GET /v1/collections/{name}`

Get a single collection by name.

**Response** `200`: Full `CollectionResponse` object.

**Errors:**

- `404` — Collection not found

#### `PUT /v1/collections/{name}`

Update a collection's description or metadata.

**Request body:**

```json
{
  "description": "Updated description",
  "metadata": {
    "team": "engineering"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `description` | string | no | New description (pass `null` to keep current) |
| `metadata` | object | no | New metadata (pass `null` to keep current) |

**Response** `200`: Updated `CollectionResponse` object.

**Errors:**

- `404` — Collection not found

#### `DELETE /v1/collections/{name}`

Delete a collection and all its documents and vectors.

**Response** `200`:

```json
{
  "status": "ok",
  "message": "Collection 'research_papers' deleted"
}
```

**Errors:**

- `404` — Collection not found

---

### Documents

Documents belong to a collection. When uploaded, they are queued for processing: parsing, chunking, embedding, and vector storage.

Base path: `/v1/collections/{collection_name}/documents`

#### `POST /v1/collections/{collection_name}/documents`

Upload a document for ingestion. Uses `multipart/form-data`.

**Request:**

```bash
curl -X POST http://localhost:6100/v1/collections/research/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -F "file=@paper.pdf" \
  -F 'metadata={"author": "Smith", "year": 2026}'
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `file` | file | yes | The document file |
| `metadata` | string (JSON) | no | JSON string of metadata to attach |

**Supported file types:** `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.htm`, `.md`, `.txt`, `.csv`, `.tsv`, `.xml`, `.json`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.gif`

**Max file size:** 500 MB (configurable via `BIGRAG_MAX_UPLOAD_SIZE_MB`)

**Response** `201`:

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "collection_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "paper.pdf",
  "file_type": "pdf",
  "file_size": 1048576,
  "chunk_count": 0,
  "status": "pending",
  "error_message": null,
  "metadata": {
    "author": "Smith",
    "year": 2026
  },
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

The document starts with `status: "pending"` and transitions to `"processing"` → `"ready"` (or `"failed"`).

**Errors:**

- `400` — Unsupported file type
- `404` — Collection not found
- `413` — File too large

#### `GET /v1/collections/{collection_name}/documents`

List documents in a collection.

**Query parameters:**

| Parameter | Type | Default | Constraints |
|-----------|------|---------|-------------|
| `status` | string | — | Filter by status: `pending`, `processing`, `ready`, `failed` |
| `limit` | integer | `100` | 1–1,000 |
| `offset` | integer | `0` | 0+ |

**Response** `200`:

```json
{
  "documents": [
    {
      "id": "...",
      "collection_id": "...",
      "filename": "paper.pdf",
      "file_type": "pdf",
      "file_size": 1048576,
      "chunk_count": 24,
      "status": "ready",
      "error_message": null,
      "metadata": {},
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 15
}
```

#### `GET /v1/collections/{collection_name}/documents/{document_id}`

Get a single document by ID.

**Response** `200`: Full `DocumentResponse` object.

**Errors:**

- `404` — Document or collection not found

#### `DELETE /v1/collections/{collection_name}/documents/{document_id}`

Delete a document and its associated vectors.

**Response** `200`:

```json
{
  "status": "ok",
  "message": "Document deleted"
}
```

**Errors:**

- `404` — Document or collection not found

#### `POST /v1/collections/{collection_name}/documents/{document_id}/reprocess`

Reprocess a document — re-parse, re-chunk, and re-embed it. Useful after changing collection settings or if processing previously failed.

**Response** `200`:

```json
{
  "status": "ok",
  "message": "Document queued for reprocessing"
}
```

**Errors:**

- `404` — Document or collection not found

#### `POST /v1/collections/{collection_name}/documents/batch/upload`

Upload multiple documents in a single request. Uses `multipart/form-data` with multiple `files` fields.

**Request:**

```bash
curl -X POST http://localhost:6100/v1/collections/research/documents/batch/upload \
  -H "Authorization: Bearer YOUR_API_SECRET" \
  -F "files=@paper1.pdf" \
  -F "files=@paper2.pdf" \
  -F "files=@notes.md" \
  -F 'metadata={"source": "batch-import"}'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file[] | Yes | Up to 100 files per request |
| `metadata` | JSON string | No | Shared metadata applied to all documents |

**Response** `201`:

```json
{
  "documents": [
    {
      "id": "...",
      "filename": "paper1.pdf",
      "status": "pending",
      ...
    },
    {
      "id": "...",
      "filename": "paper2.pdf",
      "status": "pending",
      ...
    }
  ],
  "total": 2
}
```

**Errors:**

- `400` — Unsupported file type, more than 100 files, or invalid collection
- `404` — Collection not found
- `413` — File too large

#### `POST /v1/collections/{collection_name}/documents/batch/status`

Get the processing status of multiple documents in a single request.

**Request:**

```json
{
  "document_ids": ["doc-id-1", "doc-id-2", "doc-id-3"]
}
```

**Response** `200`:

```json
{
  "documents": [
    {
      "id": "doc-id-1",
      "status": "ready",
      "error_message": null,
      "chunk_count": 24
    },
    {
      "id": "doc-id-2",
      "status": "processing",
      "error_message": null,
      "chunk_count": 0
    }
  ],
  "total": 2
}
```

Documents not found in the collection are omitted from the response.

**Errors:**

- `400` — More than 100 document IDs
- `404` — Collection not found

#### `POST /v1/collections/{collection_name}/documents/batch/delete`

Delete multiple documents in a single request.

**Request:**

```json
{
  "document_ids": [
    "doc-id-1",
    "doc-id-2",
    "doc-id-3"
  ]
}
```

**Response** `200`:

```json
{
  "status": "ok",
  "deleted": 2,
  "errors": [
    {
      "document_id": "doc-id-3",
      "error": "Document not found"
    }
  ]
}
```

Partial success is supported — documents that don't exist or fail to delete are reported in the `errors` array.

**Errors:**

- `400` — More than 100 document IDs
- `404` — Collection not found

#### `GET /v1/collections/{collection_name}/documents/{document_id}/chunks`

Get all chunks for a processed document.

**Response** `200`:

```json
{
  "chunks": [
    {
      "id": "chunk_001",
      "text": "This is the first chunk of text from the document...",
      "chunk_index": 0,
      "metadata": {
        "document_id": "...",
        "page": 1
      }
    }
  ],
  "total": 24
}
```

**Errors:**

- `404` — Document or collection not found

#### `GET /v1/collections/{collection_name}/documents/{document_id}/file`

Download the original uploaded file.

**Response** `200`: Binary file content with appropriate `Content-Type` header.

**Errors:**

- `404` — Document or collection not found

#### `GET /v1/collections/{collection_name}/documents/{document_id}/progress`

Stream real-time processing progress via Server-Sent Events (SSE).

**Response:** SSE stream

```
data: {"step": "parsing", "status": "in_progress", "message": "Parsing document with Docling", "progress": 25.0}

data: {"step": "chunking", "status": "in_progress", "message": "Splitting into 24 chunks", "progress": 50.0}

data: {"step": "embedding", "status": "in_progress", "message": "Generating embeddings", "progress": 75.0}

data: {"step": "complete", "status": "completed", "message": "Document ready", "progress": 100.0}
```

**Event fields:**

| Field | Type | Description |
|-------|------|-------------|
| `step` | string | Current processing step |
| `status` | string | Step status |
| `message` | string | Human-readable progress message |
| `progress` | float | Overall progress percentage (0–100) |

---

### Query & Search

#### `POST /v1/collections/{collection_name}/query`

Perform semantic search against a collection. The query is embedded using the collection's configured embedding model and matched against stored vectors.

**Request body:**

```json
{
  "query": "What are the main findings about climate change?",
  "top_k": 10,
  "filters": {
    "author": "Smith"
  },
  "min_score": 0.5
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `query` | string | yes | — | Natural language query text |
| `top_k` | integer | no | `10` | 1–1,000 |
| `filters` | object | no | — | Metadata filters (exact match) |
| `min_score` | float | no | — | Minimum similarity score threshold |

**Response** `200`:

```json
{
  "results": [
    {
      "id": "chunk_abc123",
      "text": "The study found significant increases in global temperatures...",
      "score": 0.892,
      "document_id": "660e8400-e29b-41d4-a716-446655440000",
      "chunk_index": 3,
      "metadata": {
        "author": "Smith",
        "page": 5
      }
    },
    {
      "id": "chunk_def456",
      "text": "These findings are consistent with previous research...",
      "score": 0.847,
      "document_id": "660e8400-e29b-41d4-a716-446655440000",
      "chunk_index": 7,
      "metadata": {
        "author": "Smith",
        "page": 12
      }
    }
  ],
  "query": "What are the main findings about climate change?",
  "collection": "research_papers",
  "total": 2
}
```

**Result fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Chunk/vector ID |
| `text` | string | The chunk text content |
| `score` | float | Similarity score (higher = more relevant) |
| `document_id` | string | Source document UUID |
| `chunk_index` | integer | Position within the source document |
| `metadata` | object | Chunk and document metadata |

**Errors:**

- `404` — Collection not found

---

### Multi-Collection Query

Query multiple collections in a single request with merged, score-sorted results.

```
POST /v1/query
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Search query |
| `collections` | string[] | Yes | Collection names to search |
| `top_k` | number | No | Max results (default 10) |
| `filters` | object | No | Metadata filters |
| `min_score` | number | No | Minimum similarity score |
| `search_mode` | string | No | `"semantic"`, `"keyword"`, or `"hybrid"` (default `"semantic"`) |

Results are merged across collections and sorted by score. Each result includes a `collection` field.

```bash
curl -X POST http://localhost:6100/v1/query \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","collections":["docs","papers"],"top_k":20}'
```

---

### Hybrid Search

All query endpoints support a `search_mode` parameter:

| Mode | Description |
|------|-------------|
| `semantic` | Default. Cosine similarity vector search. |
| `keyword` | Text-based keyword matching with term frequency scoring. |
| `hybrid` | Runs both semantic and keyword search, merges results using Reciprocal Rank Fusion (RRF). |

Hybrid mode is recommended when queries contain exact terms (product codes, IDs, names) that pure semantic search might miss.

```bash
curl -X POST http://localhost:6100/v1/collections/docs/query \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"query":"error code ERR-4021","search_mode":"hybrid"}'
```

---

### Reranking

Collections can enable server-side reranking using the Cohere Rerank API. After initial vector search, results are re-scored by a cross-encoder model for improved relevance.

**Configure per collection:**

```bash
curl -X POST http://localhost:6100/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name":"docs","reranking_enabled":true,"reranking_model":"rerank-v3.5","reranking_api_key":"your-cohere-key"}'
```

| Collection Field | Type | Default | Description |
|-----------------|------|---------|-------------|
| `reranking_enabled` | boolean | `false` | Enable reranking |
| `reranking_model` | string | `"rerank-v3.5"` | Cohere reranking model |
| `reranking_api_key` | string | null | Cohere API key (uses embedding key as fallback) |

**Override per query:** Pass `"rerank": true` or `"rerank": false` in any query request to override the collection setting.

---

### Batch Query

Run multiple independent queries in a single request. Queries execute in parallel.

```
POST /v1/batch/query
```

```json
{
  "queries": [
    {"collection": "docs", "query": "authentication", "top_k": 5},
    {"collection": "papers", "query": "neural networks", "top_k": 10, "search_mode": "hybrid"}
  ]
}
```

Maximum 20 queries per batch. Response contains an array of result sets matching the input order.

---

### Collection Analytics

Query statistics for a collection. Requires query logging (automatic).

```
GET /v1/collections/{name}/analytics
```

Returns:

```json
{
  "collection": "docs",
  "period_24h": {"query_count": 142, "avg_latency_ms": 45.2, "avg_score": 0.82, "avg_result_count": 8.3},
  "period_7d": {"query_count": 1203, "avg_latency_ms": 48.1, "avg_score": 0.79, "avg_result_count": 7.9},
  "period_30d": {"query_count": 4521, "avg_latency_ms": 46.7, "avg_score": 0.80, "avg_result_count": 8.1},
  "top_queries": [{"query": "authentication flow", "count": 23}]
}
```

---

### Vectors (Direct)

For advanced use cases, you can directly manage vectors without going through the document ingestion pipeline. This is useful for custom embeddings or integrating with external embedding services.

#### `POST /v1/collections/{collection_name}/vectors/upsert`

Insert or update vectors directly.

**Request body:**

```json
{
  "vectors": [
    {
      "id": "custom_001",
      "embedding": [0.1, 0.2, 0.3, ...],
      "text": "Custom text content",
      "metadata": {
        "source": "external"
      }
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vectors` | array | yes | List of vector entries |
| `vectors[].id` | string | yes | Unique vector ID |
| `vectors[].embedding` | array[float] | yes | Embedding vector (must match collection dimension) |
| `vectors[].text` | string | no | Associated text content |
| `vectors[].metadata` | object | no | Arbitrary metadata |

**Response** `200`:

```json
{
  "status": "ok",
  "upserted": 1
}
```

**Errors:**

- `400` — Dimension mismatch, invalid vectors
- `404` — Collection not found

#### `POST /v1/collections/{collection_name}/vectors/delete`

Delete vectors by their IDs.

**Request body:**

```json
{
  "ids": ["custom_001", "custom_002"]
}
```

**Response** `200`:

```json
{
  "status": "ok",
  "deleted": 2
}
```

**Errors:**

- `404` — Collection not found

---

### Embedding Models

#### `GET /v1/embeddings/models`

List all available embedding models and providers.

**Response** `200`:

```json
{
  "models": [
    {
      "provider": "openai",
      "model": "text-embedding-3-small",
      "dimension": 1536,
      "description": "OpenAI small embedding model"
    },
    {
      "provider": "openai",
      "model": "text-embedding-3-large",
      "dimension": 3072,
      "description": "OpenAI large embedding model"
    },
    {
      "provider": "cohere",
      "model": "embed-english-v3.0",
      "dimension": 1024,
      "description": "Cohere English embedding model"
    },
    {
      "provider": "cohere",
      "model": "embed-multilingual-v3.0",
      "dimension": 1024,
      "description": "Cohere multilingual embedding model"
    },
    {
      "provider": "cohere",
      "model": "embed-english-light-v3.0",
      "dimension": 384,
      "description": "Cohere lightweight English model"
    },
    {
      "provider": "cohere",
      "model": "embed-multilingual-light-v3.0",
      "dimension": 384,
      "description": "Cohere lightweight multilingual model"
    }
  ]
}
```

---

### Admin: Webhooks

Manage webhook registrations. Webhooks push notifications when document processing state changes. Admin access required.

**Event types:** `document.processing`, `document.ready`, `document.failed`

#### Register Webhook

```
POST /v1/admin/webhooks
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Delivery URL (must be HTTPS, HTTP allowed for localhost) |
| `events` | string[] | Yes | Event types to subscribe to |
| `collections` | string[] | No | Filter by collection names (null = all) |
| `description` | string | No | Human-readable description |

**Response (201):** Webhook object with `secret` field (shown once only). Store the secret — it's used to verify webhook signatures.

```bash
curl -X POST http://localhost:6100/v1/admin/webhooks \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/webhook","events":["document.ready","document.failed"]}'
```

#### List Webhooks

```
GET /v1/admin/webhooks?limit=50&offset=0
```

#### Get Webhook

```
GET /v1/admin/webhooks/{id}
```

#### Update Webhook

```
PUT /v1/admin/webhooks/{id}
```

Updatable fields: `url`, `events`, `collections`, `description`, `active`.

#### Delete Webhook

```
DELETE /v1/admin/webhooks/{id}
```

#### List Deliveries

```
GET /v1/admin/webhooks/{id}/deliveries?limit=50&offset=0
```

Returns delivery history for a webhook, useful for debugging.

#### Test Webhook

```
POST /v1/admin/webhooks/{id}/test
```

Sends a `webhook.test` event to verify the endpoint is reachable. Returns the delivery result inline.

#### Webhook Payload

```json
{
  "event": "document.ready",
  "timestamp": "2026-04-02T12:34:56Z",
  "collection": "docs",
  "document_id": "abc-123",
  "status": "ready",
  "chunk_count": 42,
  "error_message": null
}
```

#### Signature Verification

Each delivery includes an `X-BigRAG-Signature` header with an HMAC-SHA256 signature:

```
X-BigRAG-Signature: sha256=<hex digest>
X-BigRAG-Event: document.ready
X-BigRAG-Delivery: <delivery-uuid>
```

Verify by computing `HMAC-SHA256(webhook_secret, raw_body)` and comparing:

```python
import hmac, hashlib

def verify(payload: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

#### Retry Policy

Failed deliveries retry 3 times with exponential backoff (~10s, ~30s, ~90s). After all retries, the delivery is marked as `failed`. Check delivery history for details.

---

### Platform Stats

#### `GET /v1/stats`

Get platform-wide statistics including collections, documents, and queue.

**Response** `200`:

```json
{
  "collections": 5,
  "documents": {
    "total": 128,
    "ready": 120,
    "pending": 3,
    "processing": 2,
    "failed": 3,
    "total_chunks": 4850,
    "total_tokens": 285000,
    "total_size_bytes": 524288000
  },
  "webhooks": 2,
  "queue": {
    "queued": 150,
    "completed": 120,
    "failed": 5,
    "pending": 3,
    "processing": 2
  }
}
```

---

## Embedding Providers

bigRAG supports multiple embedding providers. Each collection can use a different provider and model.

| Provider | Model | Dimensions | Notes |
|----------|-------|------------|-------|
| **openai** | `text-embedding-3-small` (default) | 1536 | Requires `BIGRAG_EMBEDDING_API_KEY` |
| **openai** | `text-embedding-3-large` | 3072 | Best quality (OpenAI) |
| **cohere** | `embed-english-v3.0` | 1024 | Requires `BIGRAG_EMBEDDING_API_KEY` |
| **cohere** | `embed-multilingual-v3.0` | 1024 | Multilingual support |
| **cohere** | `embed-english-light-v3.0` | 384 | Lightweight English model |
| **cohere** | `embed-multilingual-light-v3.0` | 384 | Lightweight multilingual model |

**Setting per collection:**

```bash
curl -X POST http://localhost:6100/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "multilingual_docs",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "dimension": 1536
  }'
```

**Using OpenAI embeddings:**

```bash
curl -X POST http://localhost:6100/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "openai_collection",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "embedding_api_key": "sk-...",
    "dimension": 1536
  }'
```

**Using Cohere embeddings:**

```bash
curl -X POST http://localhost:6100/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cohere_collection",
    "embedding_provider": "cohere",
    "embedding_model": "embed-english-v3.0",
    "embedding_api_key": "your-cohere-api-key",
    "dimension": 1024
  }'
```

---

## Document Ingestion Pipeline

### Supported Formats

bigRAG uses [Docling](https://github.com/DS4SD/docling) for document parsing, supporting:

| Format | Extensions | Notes |
|--------|------------|-------|
| PDF | `.pdf` | With OCR for scanned documents |
| Microsoft Word | `.docx` | Full layout support |
| Microsoft PowerPoint | `.pptx` | Slide content extraction |
| Microsoft Excel | `.xlsx` | Table data extraction |
| HTML | `.html`, `.htm` | Web page content |
| Markdown | `.md` | Native support |
| Plain Text | `.txt` | Direct ingestion |
| CSV / TSV | `.csv`, `.tsv` | Tabular data |
| XML | `.xml` | Structured data |
| JSON | `.json` | Structured data |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`, `.gif` | OCR text extraction |

### How Ingestion Works

1. **Upload** — file is stored on the configured storage backend (local disk or S3)
2. **Queue** — document is added to the Redis ingestion queue with status `pending`
3. **Parse** — a background worker picks up the document and parses it with Docling
4. **Chunk** — extracted text is split into chunks based on the collection's `chunk_size` and `chunk_overlap` settings
5. **Embed** — each chunk is embedded using the collection's configured embedding model
6. **Store** — embeddings are batch-inserted into the Milvus collection
7. **Ready** — document status is updated to `ready` with the chunk count

### Chunking Strategy

Chunking splits document text into overlapping segments for embedding and retrieval.

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `chunk_size` | 512 | 64–10,000 | Maximum tokens per chunk |
| `chunk_overlap` | 50 | 0–5,000 | Overlap tokens between adjacent chunks |

- **Smaller chunks** (256–512) are better for precise answers and factual retrieval
- **Larger chunks** (1,000–2,000) provide more context per result
- **Overlap** ensures important content at chunk boundaries is not lost

These are set per collection at creation time:

```json
{
  "name": "precise_search",
  "chunk_size": 256,
  "chunk_overlap": 30
}
```

### Processing Status

Documents transition through these states:

| Status | Description |
|--------|-------------|
| `pending` | Queued, waiting for a worker |
| `processing` | Being parsed, chunked, and embedded |
| `ready` | Successfully processed, searchable |
| `failed` | Processing failed (see `error_message`) |

Filter documents by status:

```bash
# List only failed documents
curl "http://localhost:6100/v1/collections/research/documents?status=failed" \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"
```

### Real-Time Progress (SSE)

Monitor document processing in real time via Server-Sent Events:

```javascript
const eventSource = new EventSource(
  'http://localhost:6100/v1/collections/research/documents/DOC_ID/progress',
  { headers: { 'Authorization': 'Bearer TOKEN' } }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.step}: ${data.progress}% — ${data.message}`);
};
```

---

## Storage Backends

bigRAG supports two storage backends for uploaded document files.

### Local Storage (default)

Files are stored on the local filesystem.

```toml
[storage]
backend = "local"

[ingestion]
upload_dir = "./data/uploads"
```

### S3 Storage

Files are stored in an S3-compatible bucket (AWS S3, MinIO, etc.).

```toml
[storage]
backend = "s3"

[s3]
bucket = "my-bigrag-bucket"
endpoint_url = "https://s3.amazonaws.com"  # or MinIO URL
region = "us-east-1"
access_key = "AKIA..."
secret_key = "..."
```

Or via environment variables:

```bash
BIGRAG_STORAGE_BACKEND=s3
BIGRAG_S3_BUCKET=my-bigrag-bucket
BIGRAG_S3_ENDPOINT_URL=https://s3.amazonaws.com
BIGRAG_S3_REGION=us-east-1
BIGRAG_S3_ACCESS_KEY=AKIA...
BIGRAG_S3_SECRET_KEY=...
```

---

## TypeScript SDK

Zero dependencies. Works in Node.js 18+, browsers, Deno, Bun, and edge runtimes.

### Installation

```bash
npm install @bigrag/client
```

### Quick Start

```typescript
import { BigRAG } from "@bigrag/client";

const client = new BigRAG({
  apiSecret: "your-api-secret",  // omit if server has no BIGRAG_API_SECRET
  baseUrl: "http://localhost:6100",
});

// Create a collection
const collection = await client.createCollection({
  name: "knowledge_base",
  description: "Company docs",
  chunk_size: 512,
});

// Upload a document
const doc = await client.uploadDocument("knowledge_base", file);

// Stream processing progress
for await (const event of client.streamDocumentProgress("knowledge_base", doc.id)) {
  console.log(event.step, event.progress);
  if (event.status === "complete") break;
}

// Query
const { results } = await client.query("knowledge_base", {
  query: "What is the PTO policy?",
  top_k: 5,
});
```

### Configuration

| Option | Default | Description |
| --- | --- | --- |
| `apiSecret` | `BIGRAG_API_SECRET` env var | Shared API secret (omit if server is open) |
| `baseUrl` | `http://localhost:6100` | bigRAG server URL |
| `timeout` | `120000` | Request timeout in milliseconds |
| `maxRetries` | `2` | Max retries on 5xx, 429, and network errors |
| `fetch` | `globalThis.fetch` | Custom fetch implementation |

### SDK Reference

#### Collections

```typescript
client.listCollections()
client.createCollection({ name, description?, embedding_provider?, embedding_model?, dimension?, chunk_size?, chunk_overlap? })
client.getCollection(name)
client.updateCollection(name, { description?, metadata? })
client.deleteCollection(name)
```

#### Documents

```typescript
client.uploadDocument(collection, file, metadata?)
client.batchUploadDocuments(collection, files, metadata?)
client.listDocuments(collection, { status?, limit?, offset? })
client.getDocument(collection, documentId)
client.deleteDocument(collection, documentId)
client.batchGetStatus(collection, documentIds)
client.batchDeleteDocuments(collection, documentIds)
client.reprocessDocument(collection, documentId)
client.getDocumentChunks(collection, documentId)
client.getDocumentFileUrl(collection, documentId)  // returns URL string
client.streamDocumentProgress(collection, documentId)  // returns AsyncIterable<ProgressEvent>
```

File uploads accept `File`, `Blob`, `Buffer`, `Uint8Array`, or `{ path: string; name?: string }`.

#### Query & Vectors

```typescript
client.query(collection, { query, top_k?, filters?, min_score?, search_mode?, rerank? })
client.multiQuery({ query, collections, top_k?, filters?, min_score?, search_mode? })
client.batchQuery({ queries: [{ collection, query, top_k?, search_mode? }, ...] })
client.upsertVectors(collection, vectors)
client.deleteVectors(collection, ids)
client.listEmbeddingModels()
client.getStats()
```

#### Analytics

```typescript
client.getAnalytics(collection)
```

#### Scoped Collection Client

Use `client.collection(name)` to get a scoped client that omits the collection parameter from every call:

```typescript
const docs = client.collection("knowledge_base");
await docs.query({ query: "PTO policy", top_k: 5 });
await docs.upload(file);
await docs.batchUpload([file1, file2, file3]);
await docs.batchGetStatus(["doc-id-1", "doc-id-2"]);
await docs.batchDelete(["doc-id-1", "doc-id-2"]);
await docs.analytics();
```

### Error Handling

```typescript
import { BigRAG, AuthenticationError, NotFoundError, APIError } from "@bigrag/client";

try {
  await client.getCollection("missing");
} catch (err) {
  if (err instanceof NotFoundError) {
    // 404
  } else if (err instanceof AuthenticationError) {
    // 401
  } else if (err instanceof APIError) {
    // any other API error — check err.status
  }
}
```

Error hierarchy: `BigRAGError` > `APIError` > `BadRequestError` (400), `AuthenticationError` (401), `NotFoundError` (404), `RateLimitError` (429), `InternalServerError` (500). Network failures throw `APIConnectionError` or `APITimeoutError`.

### Retry Behavior

- **Retried:** HTTP 500+, HTTP 429, connection errors, timeouts
- **Not retried:** HTTP 400, 401, 403, 404
- **Backoff:** `min(0.5 * 2^attempt, 4.0)` seconds
- **Default retries:** 2 (configurable via `maxRetries`)

---

## curl Examples

### Complete Workflow

```bash
# Set your API secret (skip if BIGRAG_API_SECRET is unset on the server)
export BIGRAG_API_SECRET="your-api-secret"
export BASE="http://localhost:6100"

# 1. Check health
curl $BASE/health

# 2. Create a collection
curl -X POST $BASE/v1/collections \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "knowledge_base",
    "description": "Company knowledge base",
    "chunk_size": 512,
    "chunk_overlap": 50
  }'

# 3. Upload a document
curl -X POST $BASE/v1/collections/knowledge_base/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -F "file=@handbook.pdf" \
  -F 'metadata={"department": "engineering"}'

# 4. Check document status
curl $BASE/v1/collections/knowledge_base/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# 5. Query the collection
curl -X POST $BASE/v1/collections/knowledge_base/query \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the PTO policy?",
    "top_k": 5
  }'

# 6. Query with filters
curl -X POST $BASE/v1/collections/knowledge_base/query \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deployment process",
    "top_k": 10,
    "filters": {"department": "engineering"},
    "min_score": 0.5
  }'
```

### Document Management

```bash
# Upload multiple formats
curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" -F "file=@report.pdf"

curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" -F "file=@notes.md"

curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" -F "file=@data.csv"

# List with status filter
curl "$BASE/v1/collections/docs/documents?status=ready&limit=50" \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# Get document chunks
curl $BASE/v1/collections/docs/documents/DOC_ID/chunks \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# Download original file
curl -O $BASE/v1/collections/docs/documents/DOC_ID/file \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# Reprocess a failed document
curl -X POST $BASE/v1/collections/docs/documents/DOC_ID/reprocess \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# Batch upload multiple documents
curl -X POST $BASE/v1/collections/docs/documents/batch/upload \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -F "files=@report.pdf" \
  -F "files=@notes.md" \
  -F "files=@data.csv" \
  -F 'metadata={"source": "batch-import"}'

# Delete a document
curl -X DELETE $BASE/v1/collections/docs/documents/DOC_ID \
  -H "Authorization: Bearer $BIGRAG_API_SECRET"

# Batch check status of multiple documents
curl -X POST $BASE/v1/collections/docs/documents/batch/status \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["DOC_ID_1", "DOC_ID_2"]}'

# Batch delete multiple documents
curl -X POST $BASE/v1/collections/docs/documents/batch/delete \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["DOC_ID_1", "DOC_ID_2", "DOC_ID_3"]}'
```

### Direct Vector Operations

```bash
# Upsert custom vectors
curl -X POST $BASE/v1/collections/custom/vectors/upsert \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": [
      {
        "id": "vec_001",
        "embedding": [0.1, 0.2, 0.3],
        "text": "Custom content",
        "metadata": {"source": "external"}
      }
    ]
  }'

# Delete vectors
curl -X POST $BASE/v1/collections/custom/vectors/delete \
  -H "Authorization: Bearer $BIGRAG_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"ids": ["vec_001"]}'
```

---

## Error Codes

All API errors return a JSON body with a `detail` field:

```json
{
  "detail": "Error description"
}
```

| HTTP Status | Meaning | Common Causes |
|-------------|---------|---------------|
| `400` | Bad Request | Invalid input, missing required fields, invalid format |
| `401` | Unauthorized | Missing or invalid authentication token |
| `403` | Forbidden | Insufficient permissions (e.g., member accessing admin endpoints) |
| `404` | Not Found | Collection, document, user, or resource doesn't exist |
| `409` | Conflict | Duplicate name (e.g., collection already exists) |
| `413` | Payload Too Large | File exceeds `BIGRAG_MAX_UPLOAD_SIZE_MB` |
| `429` | Too Many Requests | Rate limited (auth endpoints: 10 req/60s per IP) |
| `500` | Internal Server Error | Server-side error |

---

## Rate Limiting

Rate limiting is per IP address. When rate limited, the API returns `429 Too Many Requests`.

---

## Deployment

### Docker Compose Production

For production deployments, create a `docker-compose.prod.yml`:

```yaml
services:
  bigrag:
    image: yoginth/bigrag:latest
    ports:
      - "6100:6100"
    environment:
      BIGRAG_DATABASE_URL: postgres://bigrag:strongpassword@postgres:5432/bigrag
      BIGRAG_MILVUS_URI: http://milvus:19530
      BIGRAG_REDIS_URL: redis://redis:6379/0
      BIGRAG_API_SECRET: your-api-secret
      BIGRAG_LOG_FORMAT: json
    depends_on:
      - postgres
      - milvus
      - redis

  postgres:
    image: postgres:17
    environment:
      POSTGRES_USER: bigrag
      POSTGRES_PASSWORD: strongpassword
      POSTGRES_DB: bigrag
    volumes:
      - pgdata:/var/lib/postgresql/data

  milvus:
    image: milvusdb/milvus:latest
    volumes:
      - milvusdata:/var/lib/milvus

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  milvusdata:
  redisdata:
```

### Environment Variables for Production

Key settings to configure for production:

```bash
# Security
BIGRAG_API_SECRET=your-api-secret         # Shared API secret (omit for open access)

# Infrastructure
BIGRAG_DATABASE_URL=postgres://user:pass@host:5432/bigrag?sslmode=require
BIGRAG_REDIS_URL=redis://redis:6379/0

# Performance
BIGRAG_WORKERS=8                          # Match CPU cores
BIGRAG_INGESTION_WORKERS=8               # More workers for heavy ingestion
BIGRAG_DB_POOL_MAX=100                   # Increase for high concurrency
BIGRAG_EMBEDDING_CONCURRENCY=16          # Parallel embedding requests
BIGRAG_MILVUS_MAX_WORKERS=64            # Milvus thread pool

# Logging
BIGRAG_LOG_FORMAT=json                    # Structured logging for production

# Storage (S3 for production)
BIGRAG_STORAGE_BACKEND=s3
BIGRAG_S3_BUCKET=your-bucket
BIGRAG_S3_REGION=us-east-1
```

---

## Troubleshooting

### Common Issues

**"Connection refused" on startup**

Ensure all infrastructure services are running and healthy:

```bash
# Check Postgres
docker exec bigrag-postgres pg_isready -U bigrag

# Check Milvus
curl -f http://localhost:9091/healthz

# Check Redis
docker exec bigrag-redis redis-cli ping
```

**Documents stuck in "pending" status**

- Verify Redis is running and accessible
- Check the backend logs for worker errors
- Ensure `BIGRAG_INGESTION_WORKERS` is > 0

**"Dimension mismatch" error on query**

The query embedding dimension doesn't match the collection's configured dimension. Ensure you're querying a collection with the same embedding model used to create it.

**File upload returns 413**

The file exceeds the max upload size. Increase `BIGRAG_MAX_UPLOAD_SIZE_MB` (default: 1024 MB).

**Slow embedding performance**

- Ensure your `BIGRAG_EMBEDDING_API_KEY` is set for OpenAI or Cohere providers
- Increase `BIGRAG_INGESTION_BATCH_SIZE` for better throughput

### Logs

Backend logs include request details, processing status, and errors:

```bash
# Development (colorized text)
BIGRAG_LOG_LEVEL=debug python -m bigrag.main

# Production (structured JSON)
BIGRAG_LOG_FORMAT=json BIGRAG_LOG_LEVEL=info python -m bigrag.main
```

### Health Check

```bash
curl http://localhost:6100/health
# → {"status":"ok","version":"0.x.x","postgres":true,"milvus":true,"redis":true}
```

If the health check returns `"status": "degraded"` with HTTP 503, one or more dependencies (Postgres, Milvus, Redis) are unreachable.

---

## Database Schema

bigRAG uses PostgreSQL for metadata. Tables are created and migrated automatically on startup.

| Table | Purpose |
|-------|---------|
| `collections` | Collection metadata (name, embedding config, chunk config) |
| `documents` | Document metadata (filename, status, chunk_count, file_path) |
| `webhooks` | Webhook registrations (url, events, collections, secret) |
| `webhook_deliveries` | Webhook delivery log (status, attempts, payload) |
| `query_log` | Query analytics log (collection, query, latency, score) |

---

*bigRAG is open-source under the [MIT License](../LICENSE). Contributions welcome.*

*If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).*
