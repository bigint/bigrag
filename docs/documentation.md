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
  - [First-Time Setup](#first-time-setup)
- [Authentication](#authentication)
  - [Authentication Modes](#authentication-modes)
  - [Session Auth (Default)](#session-auth-default)
  - [API Key Auth](#api-key-auth)
  - [Auth Priority](#auth-priority)
- [Configuration](#configuration)
  - [TOML Configuration](#toml-configuration)
  - [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
  - [Health & Metrics](#health--metrics)
  - [Auth Endpoints](#auth-endpoints)
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
  - [Admin: API Keys](#admin-api-keys)
  - [Admin: Webhooks](#admin-webhooks)
  - [Queue](#queue)
- [Embedding Providers](#embedding-providers)
- [Document Ingestion Pipeline](#document-ingestion-pipeline)
  - [Supported Formats](#supported-formats)
  - [How Ingestion Works](#how-ingestion-works)
  - [Chunking Strategy](#chunking-strategy)
  - [Processing Status](#processing-status)
  - [Real-Time Progress (SSE)](#real-time-progress-sse)
- [Storage Backends](#storage-backends)
- [Python SDK](#python-sdk)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Synchronous Client](#synchronous-client)
  - [Asynchronous Client](#asynchronous-client)
  - [SDK Reference](#sdk-reference)
  - [Error Handling](#error-handling)
  - [Retry Behavior](#retry-behavior)
- [TypeScript SDK](#typescript-sdk)
- [Go SDK](#go-sdk)
- [curl Examples](#curl-examples)
- [Admin UI](#admin-ui)
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
- **Admin web UI** — manage collections, upload documents, query, and administer users
- **Self-hostable** — Docker Compose, no external dependencies
- **User auth** — session-based auth, API keys, and role-based access
- **MIT licensed** — run it anywhere, forever free

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      bigRAG API                            │
│                    (Python / FastAPI)                       │
├───────────┬────────────┬───────────────┬──────────────────┤
│   Auth    │ Ingestion  │    Query      │     Admin        │
│  Service  │  Service   │   Service     │    Service       │
├───────────┴────────────┴───────────────┴──────────────────┤
│                                                            │
│  ┌──────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ Postgres │  │    Docling    │  │  Embedding Model  │   │
│  │ (auth +  │  │  (document    │  │ (OpenAI,           │   │
│  │ metadata)│  │   converter)  │  │  Cohere)           │   │
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
| **bigRAG API** | REST API server (FastAPI) | `http://localhost:6000` |
| **Admin UI** | Web dashboard (Next.js) | `http://localhost:3000` |
| **PostgreSQL** | User auth, metadata, sessions | `localhost:5432` |
| **Milvus** | Vector storage and search | `localhost:19530` |
| **Redis** | Ingestion job queue | `localhost:6379` |

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** (recommended method)
- **Python 3.12+** (for running from source)
- **Node.js 22+** and **pnpm** (for the admin UI)

### Docker Compose (Recommended)

```bash
docker compose up -d
```

This starts the full stack:

- **Admin UI** on port 5000
- **bigRAG API** on port 6000 (Swagger docs at `/docs`)
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
  --database-url "postgres://bigrag:bigrag@localhost:5432/bigrag" \
  --milvus-uri "http://localhost:19530"

# 3. Start the UI (in a separate terminal)
cd ui && pnpm install && pnpm dev
```

### Development Mode

The easiest way to start everything for development:

```bash
./dev.sh
```

This script:

1. Kills stale processes on ports 6000 and 3000
2. Validates required commands (`docker`, `python3`, `pnpm`, `curl`)
3. Starts Docker services (Postgres, Redis, Milvus) and waits for readiness
4. Creates a Python virtualenv and installs dependencies
5. Starts the backend with auto-reload
6. Installs UI dependencies and starts the Next.js dev server
7. Logs output with `[backend]` and `[ui]` prefixes
8. Gracefully stops everything on Ctrl+C

### First-Time Setup

On first launch, bigRAG requires an initial admin account:

1. Open `http://localhost:3000` — the UI redirects to `/setup`
2. Enter an email, password (8+ characters), and display name
3. This creates the first admin user

After setup, users log in with email/password.

Alternatively, via the API:

```bash
curl -X POST http://localhost:6000/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "secretpass", "display_name": "Admin"}'
```

### Verify

```bash
curl http://localhost:6000/health
# → {"status": "ok", "version": "0.x.x"}
```

---

## Authentication

### Authentication Modes

bigRAG supports two authentication modes:

| Mode | Config | Behavior |
|------|--------|----------|
| **User auth** (default) | `BIGRAG_AUTH_REQUIRED=true` | Login required, DB-managed API keys, roles (admin/member) |
| **No auth** | `BIGRAG_AUTH_REQUIRED=false` | All requests allowed as anonymous admin (self-hosted) |

### Session Auth (Default)

Session-based auth is the default when `BIGRAG_AUTH_REQUIRED=true`. Users authenticate via login and receive a session token.

```bash
# Login
curl -X POST http://localhost:6000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Response
{
  "token": "ses_abc123...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "display_name": "User",
    "role": "admin",
    "created_at": "2026-04-01T00:00:00Z",
    "updated_at": "2026-04-01T00:00:00Z"
  }
}

# Use the token in subsequent requests
curl http://localhost:6000/v1/collections \
  -H "Authorization: Bearer ses_abc123..."
```

Sessions expire after 168 hours (7 days) by default, configurable via `BIGRAG_SESSION_EXPIRY_HOURS`.

### API Key Auth

API keys provide scoped, long-lived access. They can be created by admins and have granular permissions.

```bash
# Use an API key
curl http://localhost:6000/v1/collections \
  -H "Authorization: Bearer bgr_abc123..."
```

API key permissions control:

- **Collections**: Which collections the key can access (empty = all)
- **Operations**: Which operations are allowed (empty = all)
- **Admin**: Whether the key has admin privileges
- **Expiry**: Optional expiration date

### Auth Priority

When auth is enabled, bigRAG evaluates tokens in this order:

1. **Session token** — validated against database
2. **API key** — validated against database with scoped permissions
3. **No token** — allowed only during initial setup (before first user is created)

All authenticated requests use the `Authorization: Bearer <token>` header.

---

## Configuration

bigRAG reads configuration from a `bigrag.toml` file and/or environment variables. Environment variables take precedence over TOML values.

### TOML Configuration

Create a `bigrag.toml` file in the project root:

```toml
[server]
host = "0.0.0.0"
port = 6000
workers = 1
log_level = "info"          # debug, info, warning, error
log_format = "text"         # text, json
cors_origins = ["*"]

[database]
url = "postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
pool_min = 5
pool_max = 50

[milvus]
uri = "http://localhost:19530"

[redis]
url = "redis://localhost:6379/0"

[auth]
auth_required = true        # Set to false to disable authentication
secret_key = ""             # Encryption key for secrets at rest
session_expiry_hours = 168  # Session lifetime (7 days)

[embedding]
provider = "openai"
model = "text-embedding-3-small"
dimension = 1536
api_key = ""                # For OpenAI/Cohere providers

[ingestion]
workers = 4
batch_size = 128
chunk_size = 512
chunk_overlap = 50
upload_dir = "./data/uploads"
max_upload_size_mb = 500

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
| `BIGRAG_HOST` | Bind address | `0.0.0.0` |
| `BIGRAG_PORT` | Server port | `6000` |
| `BIGRAG_WORKERS` | Uvicorn workers | `1` |
| `BIGRAG_LOG_LEVEL` | Log level (`debug`, `info`, `warning`, `error`) | `info` |
| `BIGRAG_LOG_FORMAT` | Log format (`text`, `json`) | `text` |
| `BIGRAG_CORS_ORIGINS` | CORS allowed origins (JSON array) | `["*"]` |
| **Database** | | |
| `BIGRAG_DATABASE_URL` | Postgres connection URL | `postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable` |
| `BIGRAG_DB_POOL_MIN` | Min DB pool size | `5` |
| `BIGRAG_DB_POOL_MAX` | Max DB pool size | `50` |
| **Milvus** | | |
| `BIGRAG_MILVUS_URI` | Milvus connection URI | `http://localhost:19530` |
| **Redis** | | |
| `BIGRAG_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| **Auth** | | |
| `BIGRAG_AUTH_REQUIRED` | Enable/disable authentication | `true` |
| `BIGRAG_SECRET_KEY` | Encryption key for secrets at rest | — |
| `BIGRAG_SESSION_EXPIRY_HOURS` | Session token lifetime | `168` |
| **Embedding** | | |
| `BIGRAG_EMBEDDING_PROVIDER` | Default embedding provider | `openai` |
| `BIGRAG_EMBEDDING_MODEL` | Default embedding model | `text-embedding-3-small` |
| `BIGRAG_EMBEDDING_DIMENSION` | Default embedding dimension | `1536` |
| `BIGRAG_EMBEDDING_API_KEY` | API key for OpenAI/Cohere | — |
| **Ingestion** | | |
| `BIGRAG_CHUNK_SIZE` | Default chunk size (tokens) | `512` |
| `BIGRAG_CHUNK_OVERLAP` | Default chunk overlap (tokens) | `50` |
| `BIGRAG_MAX_UPLOAD_SIZE_MB` | Max upload file size in MB | `500` |
| `BIGRAG_INGESTION_WORKERS` | Background processing workers | `4` |
| `BIGRAG_INGESTION_BATCH_SIZE` | Embedding batch size | `128` |
| **Storage** | | |
| `BIGRAG_STORAGE_BACKEND` | Storage backend (`local`, `s3`) | `local` |
| `BIGRAG_UPLOAD_DIR` | Local upload directory | `./data/uploads` |
| `BIGRAG_S3_BUCKET` | S3 bucket name | — |
| `BIGRAG_S3_ENDPOINT_URL` | S3 endpoint URL | — |
| `BIGRAG_S3_REGION` | S3 region | `us-east-1` |
| `BIGRAG_S3_ACCESS_KEY` | S3 access key | — |
| `BIGRAG_S3_SECRET_KEY` | S3 secret key | — |

---

## API Reference

All API endpoints are prefixed with `/v1` (except `/health`). Authentication is required for most endpoints — pass a Bearer token via the `Authorization` header.

Base URL: `http://localhost:6000`

Interactive Swagger docs: `http://localhost:6000/docs`

### Health & Metrics

#### `GET /health`

Health check. No authentication required.

**Response:**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

#### `GET /v1/metrics`

Prometheus-format metrics. Requires admin authentication.

**Response:** Prometheus text format with request counts, latencies, etc.

#### `GET /v1/queue/stats`

Ingestion queue statistics. Requires authentication.

**Response:**

```json
{
  "pending": 3,
  "processing": 1,
  "completed": 42,
  "failed": 0
}
```

---

### Auth Endpoints

Base path: `/v1/auth`

#### `GET /v1/auth/setup-status`

Check whether initial setup is needed. No authentication required.

**Response:**

```json
{
  "needs_setup": true,
  "auth_required": true
}
```

#### `POST /v1/auth/setup`

Create the initial admin account. Only works when no users exist. Rate limited (10 requests per 60 seconds per IP).

**Request body:**

```json
{
  "email": "admin@example.com",
  "password": "minimum8chars",
  "display_name": "Admin User"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string | yes | Valid email address, unique |
| `password` | string | yes | Minimum 8 characters |
| `display_name` | string | yes | Display name |

**Response** `201`:

```json
{
  "token": "ses_abc123...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@example.com",
    "display_name": "Admin User",
    "role": "admin",
    "created_at": "2026-04-01T00:00:00Z",
    "updated_at": "2026-04-01T00:00:00Z"
  }
}
```

**Errors:**

- `400` — Setup already completed (users exist)
- `429` — Rate limited

#### `POST /v1/auth/login`

Log in with email and password. Rate limited.

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "password"
}
```

**Response** `200`:

```json
{
  "token": "ses_abc123...",
  "user": {
    "id": "...",
    "email": "user@example.com",
    "display_name": "User",
    "role": "member",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

**Errors:**

- `401` — Invalid email or password
- `429` — Rate limited

#### `POST /v1/auth/logout`

Log out and invalidate the current session. Requires authentication.

**Response** `200`:

```json
{
  "status": "ok"
}
```

#### `GET /v1/auth/me`

Get the current authenticated user's information.

**Response** `200`:

```json
{
  "user": {
    "id": "...",
    "email": "user@example.com",
    "display_name": "User",
    "role": "admin",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

#### `PUT /v1/auth/password`

Change the current user's password. Requires authentication.

**Request body:**

```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword8+"
}
```

**Response** `200`:

```json
{
  "status": "ok"
}
```

**Errors:**

- `400` — New password too short (< 8 characters)
- `401` — Current password incorrect

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
curl -X POST http://localhost:6000/v1/collections/research/documents \
  -H "Authorization: Bearer $TOKEN" \
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
curl -X POST http://localhost:6000/v1/query \
  -H "Authorization: Bearer $TOKEN" \
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
curl -X POST http://localhost:6000/v1/collections/docs/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"error code ERR-4021","search_mode":"hybrid"}'
```

---

### Reranking

Collections can enable server-side reranking using the Cohere Rerank API. After initial vector search, results are re-scored by a cross-encoder model for improved relevance.

**Configure per collection:**

```bash
curl -X POST http://localhost:6000/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
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

### Admin: API Keys

Requires admin role.

#### `POST /v1/admin/api-keys`

Create a scoped API key.

**Request body:**

```json
{
  "name": "CI Pipeline Key",
  "collections": ["research_papers", "documentation"],
  "operations": ["query", "list_documents"],
  "admin": false,
  "expires_at": "2027-01-01T00:00:00Z"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Human-readable key name |
| `collections` | array[string] | no | `[]` | Allowed collections (empty = all) |
| `operations` | array[string] | no | `[]` | Allowed operations (empty = all) |
| `admin` | boolean | no | `false` | Whether key has admin privileges |
| `expires_at` | datetime | no | — | Optional expiration (ISO 8601) |

**Response** `201`:

```json
{
  "id": "...",
  "name": "CI Pipeline Key",
  "prefix": "bgr_abc",
  "key": "bgr_abc123def456ghi789...",
  "permissions": {
    "collections": ["research_papers", "documentation"],
    "operations": ["query", "list_documents"],
    "admin": false
  },
  "created_at": "2026-04-01T00:00:00Z",
  "last_used_at": null,
  "expires_at": "2027-01-01T00:00:00Z"
}
```

> **Important:** The `key` field is only returned once at creation time. Store it securely — it cannot be retrieved later.

#### `GET /v1/admin/api-keys`

List all API keys (keys are not included, only prefixes).

**Query parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `limit` | integer | `100` |
| `offset` | integer | `0` |

**Response** `200`:

```json
{
  "keys": [
    {
      "id": "...",
      "name": "CI Pipeline Key",
      "prefix": "bgr_abc",
      "key": null,
      "permissions": {
        "collections": ["research_papers"],
        "operations": [],
        "admin": false
      },
      "created_at": "...",
      "last_used_at": "2026-04-01T12:00:00Z",
      "expires_at": null
    }
  ]
}
```

#### `DELETE /v1/admin/api-keys/{key_id}`

Revoke an API key.

**Response** `200`:

```json
{
  "status": "ok",
  "message": "API key deleted"
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
curl -X POST http://localhost:6000/v1/admin/webhooks \
  -H "Authorization: Bearer $TOKEN" \
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

### Queue

#### `GET /v1/queue/stats`

Get ingestion queue statistics.

**Response** `200`:

```json
{
  "pending": 3,
  "processing": 1,
  "completed": 42,
  "failed": 0
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
curl -X POST http://localhost:6000/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
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
curl -X POST http://localhost:6000/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
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
curl -X POST http://localhost:6000/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
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
curl "http://localhost:6000/v1/collections/research/documents?status=failed" \
  -H "Authorization: Bearer $TOKEN"
```

### Real-Time Progress (SSE)

Monitor document processing in real time via Server-Sent Events:

```javascript
const eventSource = new EventSource(
  'http://localhost:6000/v1/collections/research/documents/DOC_ID/progress',
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

## Python SDK

The official Python SDK provides both synchronous and asynchronous clients.

### Installation

```bash
pip install bigrag
```

### Quick Start

```python
from bigrag import BigRAG

# Initialize client
client = BigRAG(api_key="your-api-key", base_url="http://localhost:6000")

# Create a collection
collection = client.create_collection(
    name="research",
    description="Research papers",
    embedding_model="text-embedding-3-small"
)

# Upload a document
doc = client.upload_document("research", "paper.pdf", metadata={"year": 2026})

# Query the collection
results = client.query("research", "What are the main findings?", top_k=5)
for result in results.results:
    print(f"Score: {result.score:.3f} — {result.text[:100]}...")

# Clean up
client.close()
```

### Synchronous Client

```python
from bigrag import BigRAG

# Using context manager (recommended)
with BigRAG(api_key="...", base_url="http://localhost:6000") as client:
    health = client.health()
    collections = client.list_collections()
```

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | str | `None` | API key (or set `BIGRAG_API_KEY` env var) |
| `base_url` | str | `http://localhost:6000` | bigRAG server URL |
| `timeout` | float | `120.0` | Request timeout in seconds |
| `max_retries` | int | `2` | Maximum retry attempts |

### Asynchronous Client

```python
from bigrag import AsyncBigRAG
import asyncio

async def main():
    async with AsyncBigRAG(api_key="...", base_url="http://localhost:6000") as client:
        # All methods are async
        health = await client.health()
        collections = await client.list_collections()

        # Upload and query
        doc = await client.upload_document("research", "paper.pdf")
        results = await client.query("research", "key findings", top_k=5)

asyncio.run(main())
```

### SDK Reference

Both `BigRAG` and `AsyncBigRAG` expose identical methods (async versions use `await`).

#### Health

```python
client.health() → dict
# Returns: {"status": "ok", "version": "0.x.x"}
```

#### Collections

```python
# List all collections
client.list_collections() → CollectionListResponse
# Returns: CollectionListResponse(collections=[Collection, ...])

# Create a collection
client.create_collection(
    name: str,
    description: str = "",
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
    dimension: int | None = None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) → Collection

# Get a collection
client.get_collection(name: str) → Collection

# Delete a collection
client.delete_collection(name: str) → dict
```

#### Documents

```python
# Upload a document
client.upload_document(
    collection: str,
    file_path: str | Path,
    metadata: dict | None = None,
) → Document

# List documents
client.list_documents(
    collection: str,
    status: str | None = None,
) → DocumentListResponse

# Get a document
client.get_document(collection: str, document_id: str) → Document

# Delete a document
client.delete_document(collection: str, document_id: str) → dict

# Reprocess a document
client.reprocess_document(collection: str, document_id: str) → dict
```

#### Query

```python
# Search a collection
client.query(
    collection: str,
    query: str,
    top_k: int = 10,
    filters: dict | None = None,
    min_score: float | None = None,
) → QueryResponse
# Returns: QueryResponse(results=[QueryResult, ...], query, collection, total)
```

#### Vectors

```python
# Upsert raw vectors
client.upsert_vectors(
    collection: str,
    vectors: list[dict],
) → dict
# Each vector: {"id": "...", "embedding": [...], "text": "...", "metadata": {...}}

# Delete vectors by ID
client.delete_vectors(collection: str, ids: list[str]) → dict
```

#### Connection Management

```python
# Explicit close
client.close()

# Context manager (recommended)
with BigRAG(...) as client:
    ...

# Async context manager
async with AsyncBigRAG(...) as client:
    ...
```

### Error Handling

The SDK raises typed exceptions for all error conditions:

```python
from bigrag import BigRAG
from bigrag.errors import (
    BigRAGError,         # Base exception
    APIError,            # API returned an error (base)
    BadRequestError,     # 400
    AuthenticationError, # 401
    NotFoundError,       # 404
    RateLimitError,      # 429
    InternalServerError, # 500
    APIConnectionError,  # Connection failed
    APITimeoutError,     # Request timed out
)

client = BigRAG(api_key="...")

try:
    collection = client.get_collection("nonexistent")
except NotFoundError as e:
    print(f"Not found: {e.message}")
except AuthenticationError:
    print("Invalid API key")
except APIConnectionError:
    print("Cannot connect to bigRAG server")
except APITimeoutError:
    print("Request timed out")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

**Exception hierarchy:**

```
BigRAGError
├── APIError
│   ├── BadRequestError      (400)
│   ├── AuthenticationError  (401)
│   ├── NotFoundError        (404)
│   ├── RateLimitError       (429)
│   └── InternalServerError  (500)
├── APIConnectionError
└── APITimeoutError
```

### Retry Behavior

The SDK automatically retries on transient failures:

- **Retried:** HTTP 500+, HTTP 429 (rate limited), connection errors, timeouts
- **Not retried:** HTTP 400, 401, 403, 404 (client errors)
- **Backoff:** Exponential with formula `min(0.5 * 2^attempt, 4.0)` seconds
- **Default retries:** 2 (configurable via `max_retries`)

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
  apiKey: "your-api-key",
  baseUrl: "http://localhost:6000",
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
| `apiKey` | `BIGRAG_API_KEY` env var | API key or session token |
| `baseUrl` | `http://localhost:6000` | bigRAG server URL |
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
client.listDocuments(collection, { status?, limit?, offset? })
client.getDocument(collection, documentId)
client.deleteDocument(collection, documentId)
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
client.getMetrics()
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
await docs.uploadDocument(file);
await docs.getAnalytics();
```

#### Auth & Admin

```typescript
client.getSetupStatus()
client.setup({ email, password, display_name })
client.login({ email, password })
client.logout()
client.getMe()
client.changePassword({ current_password, new_password })
client.createApiKey({ name, collections?, operations?, admin?, expires_at? })
client.listApiKeys()
client.revokeApiKey(id)
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

Same as the Python SDK:

- **Retried:** HTTP 500+, HTTP 429, connection errors, timeouts
- **Not retried:** HTTP 400, 401, 403, 404
- **Backoff:** `min(0.5 * 2^attempt, 4.0)` seconds
- **Default retries:** 2 (configurable via `maxRetries`)

---

## Go SDK

Install the Go SDK:

```bash
go get github.com/bigrag-io/bigrag-go
```

> Note: The Go SDK is under development. Check the repository for availability.

---

## curl Examples

### Complete Workflow

```bash
# Set your auth token
export TOKEN="your-api-key-or-session-token"
export BASE="http://localhost:6000"

# 1. Check health
curl $BASE/health

# 2. Create a collection
curl -X POST $BASE/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "knowledge_base",
    "description": "Company knowledge base",
    "chunk_size": 512,
    "chunk_overlap": 50
  }'

# 3. Upload a document
curl -X POST $BASE/v1/collections/knowledge_base/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@handbook.pdf" \
  -F 'metadata={"department": "engineering"}'

# 4. Check document status
curl $BASE/v1/collections/knowledge_base/documents \
  -H "Authorization: Bearer $TOKEN"

# 5. Query the collection
curl -X POST $BASE/v1/collections/knowledge_base/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the PTO policy?",
    "top_k": 5
  }'

# 6. Query with filters
curl -X POST $BASE/v1/collections/knowledge_base/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "deployment process",
    "top_k": 10,
    "filters": {"department": "engineering"},
    "min_score": 0.5
  }'
```

### Auth Operations

```bash
# Initial setup (first run only)
curl -X POST $BASE/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@co.com", "password": "securepass", "display_name": "Admin"}'

# Login
curl -X POST $BASE/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@co.com", "password": "securepass"}'

# Get current user
curl $BASE/v1/auth/me -H "Authorization: Bearer $TOKEN"

# Change password
curl -X PUT $BASE/v1/auth/password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "oldpass", "new_password": "newpass123"}'

# Logout
curl -X POST $BASE/v1/auth/logout -H "Authorization: Bearer $TOKEN"
```

### Admin Operations

```bash
# Create an API key
curl -X POST $BASE/v1/admin/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Read-only key",
    "collections": ["knowledge_base"],
    "operations": ["query"]
  }'

# List API keys
curl $BASE/v1/admin/api-keys -H "Authorization: Bearer $TOKEN"

# Revoke an API key
curl -X DELETE $BASE/v1/admin/api-keys/KEY_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Document Management

```bash
# Upload multiple formats
curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@report.pdf"

curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@notes.md"

curl -X POST $BASE/v1/collections/docs/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@data.csv"

# List with status filter
curl "$BASE/v1/collections/docs/documents?status=ready&limit=50" \
  -H "Authorization: Bearer $TOKEN"

# Get document chunks
curl $BASE/v1/collections/docs/documents/DOC_ID/chunks \
  -H "Authorization: Bearer $TOKEN"

# Download original file
curl -O $BASE/v1/collections/docs/documents/DOC_ID/file \
  -H "Authorization: Bearer $TOKEN"

# Reprocess a failed document
curl -X POST $BASE/v1/collections/docs/documents/DOC_ID/reprocess \
  -H "Authorization: Bearer $TOKEN"

# Delete a document
curl -X DELETE $BASE/v1/collections/docs/documents/DOC_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Direct Vector Operations

```bash
# Upsert custom vectors
curl -X POST $BASE/v1/collections/custom/vectors/upsert \
  -H "Authorization: Bearer $TOKEN" \
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
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ids": ["vec_001"]}'
```

---

## Admin UI

bigRAG includes a web-based admin dashboard at `http://localhost:3000`.

**Features:**

- **Dashboard** — overview of collections, documents, and system status
- **Collections** — create, view, update, and delete collections
- **Documents** — upload, list, view status, download, and manage documents
- **Query** — interactive search interface for testing queries
- **API Keys** — create and manage API keys (admin only)
- **Metrics** — Prometheus metrics dashboard
- **Settings** — server connection and account settings

The UI communicates with the bigRAG API and requires the backend to be running.

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

Rate limiting is applied to authentication endpoints to prevent brute-force attacks:

| Endpoints | Limit | Window |
|-----------|-------|--------|
| `/v1/auth/setup`, `/v1/auth/login` | 10 requests | 60 seconds |

Rate limiting is per IP address. When rate limited, the API returns `429 Too Many Requests`.

---

## Deployment

### Docker Compose Production

For production deployments, create a `docker-compose.prod.yml`:

```yaml
services:
  bigrag:
    image: bigrag/bigrag:latest
    ports:
      - "6000:6000"
    environment:
      BIGRAG_DATABASE_URL: postgres://bigrag:strongpassword@postgres:5432/bigrag
      BIGRAG_MILVUS_URI: http://milvus:19530
      BIGRAG_REDIS_URL: redis://redis:6379/0
      BIGRAG_SECRET_KEY: your-secret-encryption-key
      BIGRAG_LOG_LEVEL: info
      BIGRAG_LOG_FORMAT: json
      BIGRAG_EMBEDDING_PROVIDER: openai
      BIGRAG_EMBEDDING_MODEL: text-embedding-3-small
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
BIGRAG_SECRET_KEY=strong-random-key       # Encryption key for secrets at rest
BIGRAG_CORS_ORIGINS='["https://your-domain.com"]'  # Restrict CORS

# Database
BIGRAG_DATABASE_URL=postgres://user:pass@host:5432/bigrag?sslmode=require
BIGRAG_DB_POOL_MIN=10
BIGRAG_DB_POOL_MAX=100

# Performance
BIGRAG_WORKERS=4                          # Match CPU cores
BIGRAG_INGESTION_WORKERS=8               # More workers for heavy ingestion
BIGRAG_INGESTION_BATCH_SIZE=256          # Larger batches for throughput

# Logging
BIGRAG_LOG_FORMAT=json                    # Structured logging for production
BIGRAG_LOG_LEVEL=info

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

The file exceeds the max upload size. Increase `BIGRAG_MAX_UPLOAD_SIZE_MB` (default: 500 MB).

**"needs_setup" is always true**

The database may not be initialized. Ensure `BIGRAG_DATABASE_URL` is set and Postgres is accessible. Tables are created automatically on startup.

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
curl http://localhost:6000/health
# → {"status": "ok", "version": "0.x.x"}
```

If the health check fails, the API server is not running or not accessible on the configured port.

---

## Database Schema

bigRAG uses PostgreSQL for metadata and authentication. Tables are created and migrated automatically on startup.

| Table | Purpose |
|-------|---------|
| `users` | User accounts (id, email, password_hash, display_name, role) |
| `sessions` | Active login sessions (token_hash, user_id, expires_at) |
| `api_keys` | API keys (key_hash, prefix, permissions, expires_at) |
| `collections` | Collection metadata (name, embedding config, chunk config) |
| `documents` | Document metadata (filename, status, chunk_count, file_path) |
| `webhooks` | Webhook registrations (url, events, collections, secret) |
| `webhook_deliveries` | Webhook delivery log (status, attempts, payload) |
| `query_log` | Query analytics log (collection, query, latency, score) |

---

*bigRAG is open-source under the [MIT License](../LICENSE). Contributions welcome.*

*If bigRAG is useful to you, consider [sponsoring the project](https://github.com/sponsors/bigint).*
