# bigRAG Rust SDK Design Spec

**Date**: 2026-04-10
**Status**: Approved
**Crate name**: `bigrag`
**Location**: `sdks/rust/`

## Overview

A Rust client SDK for the bigRAG platform with full API parity with the existing TypeScript (`@bigrag/client`) and Python (`bigrag`) SDKs. Follows the Stripe-style resource namespace pattern, async-first design on Tokio, and targets crates.io publication.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Async runtime | Tokio only | De facto standard, reqwest depends on it |
| HTTP client | reqwest | Most popular, multipart support, TLS, great ergonomics |
| Crate name | `bigrag` | Matches Python SDK naming |
| MSRV | 1.75+ | `async fn` in traits stabilized, no `async-trait` macro needed |
| Sync support | Async only | Clean API, matches TS/Python SDKs, users can `block_on()` |
| Architecture | Resource namespaces via borrowed references | Matches TS/Python pattern, idiomatic Rust |
| Publishing | crates.io | Proper metadata, docs.rs, semver from start |

## Crate Structure

```
sdks/rust/
├── Cargo.toml
├── src/
│   ├── lib.rs              # Public exports, #![warn(missing_docs)]
│   ├── client.rs           # BigRag, BigRagBuilder, BigRagConfig, CollectionClient
│   ├── core.rs             # Transport layer (HTTP requests, retry, auth)
│   ├── error.rs            # BigRagError enum
│   ├── files.rs            # FileInput enum and conversions
│   ├── sse.rs              # SseStream (implements futures_core::Stream)
│   ├── resources/
│   │   ├── mod.rs
│   │   ├── collections.rs
│   │   ├── documents.rs
│   │   ├── queries.rs
│   │   ├── vectors.rs
│   │   └── webhooks.rs
│   └── types/
│       ├── mod.rs
│       ├── collections.rs
│       ├── documents.rs
│       ├── query.rs
│       ├── vectors.rs
│       ├── webhooks.rs
│       ├── common.rs
│       ├── analytics.rs
│       ├── embeddings.rs
│       └── sse.rs
├── tests/
│   ├── client.rs
│   ├── resources.rs
│   └── helpers.rs
├── examples/
│   ├── basic_usage.rs
│   └── file_upload.rs
└── README.md
```

## Dependencies

```toml
[dependencies]
reqwest = { version = "0.12", features = ["json", "multipart", "stream"] }
tokio = { version = "1", features = ["fs"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2"
futures-core = "0.3"
pin-project-lite = "0.2"

[dev-dependencies]
tokio = { version = "1", features = ["full"] }
futures-util = "0.3"
wiremock = "0.6"
```

## Client Construction

### BigRag

The main entry point. Holds a `reqwest::Client`, base URL, API key, and config.

```rust
// Simple
let client = BigRag::new("http://localhost:6100", "sk-...");

// From environment (BIGRAG_BASE_URL + BIGRAG_API_KEY)
let client = BigRag::from_env()?;

// Builder for full control
let client = BigRag::builder()
    .base_url("https://bigrag.example.com")
    .api_key("sk-...")
    .timeout(Duration::from_secs(60))
    .max_retries(3)
    .reqwest_client(custom_client)  // bring your own
    .build()?;
```

### Defaults

- `base_url`: `http://localhost:6100`
- `timeout`: 120 seconds
- `max_retries`: 2

### Resource Access

```rust
client.collections()   // -> Collections<'_>
client.documents()     // -> Documents<'_>
client.queries()       // -> Queries<'_>
client.vectors()       // -> Vectors<'_>
client.webhooks()      // -> Webhooks<'_>
client.collection("x") // -> CollectionClient<'_> (scoped convenience)
```

### Platform Methods (directly on BigRag)

```rust
client.health()            // -> HealthResponse
client.readiness()         // -> ReadinessResponse
client.stats()             // -> PlatformStatsResponse
client.embedding_models()  // -> EmbeddingModelListResponse
```

## Resource Namespaces

Each resource is a zero-cost borrowed struct: `struct Collections<'a> { client: &'a BigRag }`.

### Collections

| Method | Signature |
|--------|-----------|
| `list` | `(options: Option<CollectionListOptions>) -> Result<CollectionListResponse>` |
| `get` | `(name: &str) -> Result<Collection>` |
| `create` | `(body: CreateCollectionBody) -> Result<Collection>` |
| `update` | `(name: &str, body: UpdateCollectionBody) -> Result<Collection>` |
| `delete` | `(name: &str) -> Result<StatusResponse>` |
| `stats` | `(name: &str) -> Result<CollectionStatsResponse>` |
| `truncate` | `(name: &str) -> Result<StatusResponse>` |
| `stream_events` | `(name: &str) -> impl Stream<Item = Result<ProgressEvent>>` |

### Documents

| Method | Signature |
|--------|-----------|
| `upload` | `(collection: &str, file: impl Into<FileInput>, metadata: Option<Value>) -> Result<Document>` |
| `batch_upload` | `(collection: &str, files: Vec<FileInput>, metadata: Option<Value>) -> Result<DocumentListResponse>` |
| `list` | `(collection: &str, options: Option<DocumentListOptions>) -> Result<DocumentListResponse>` |
| `get` | `(collection: &str, document_id: &str) -> Result<Document>` |
| `delete` | `(collection: &str, document_id: &str) -> Result<StatusResponse>` |
| `reprocess` | `(collection: &str, document_id: &str) -> Result<StatusResponse>` |
| `get_chunks` | `(collection: &str, document_id: &str) -> Result<DocumentChunkListResponse>` |
| `get_file_url` | `(collection: &str, document_id: &str) -> String` |
| `batch_get_status` | `(collection: &str, document_ids: &[&str]) -> Result<BatchStatusResponse>` |
| `batch_get` | `(collection: &str, document_ids: &[&str]) -> Result<BatchGetDocumentsResponse>` |
| `batch_delete` | `(collection: &str, document_ids: &[&str]) -> Result<BatchDeleteDocumentsResponse>` |
| `ingest_s3` | `(collection: &str, body: S3IngestBody) -> Result<S3IngestResponse>` |
| `list_s3_jobs` | `(collection: &str) -> Result<S3JobListResponse>` |
| `delete_s3_job` | `(collection: &str, job_id: &str) -> Result<StatusResponse>` |
| `resync_s3_job` | `(collection: &str, job_id: &str) -> Result<StatusResponse>` |
| `get_by_id` | `(document_id: &str) -> Result<Document>` |
| `get_chunks_by_id` | `(document_id: &str) -> Result<DocumentChunkListResponse>` |
| `stream_progress` | `(collection: &str, document_id: &str) -> impl Stream<Item = Result<ProgressEvent>>` |
| `stream_batch_progress` | `(collection: &str, document_ids: &[&str]) -> impl Stream<Item = Result<ProgressEvent>>` |

### Queries

| Method | Signature |
|--------|-----------|
| `query` | `(collection: &str, body: QueryBody) -> Result<QueryResponse>` |
| `multi_query` | `(body: MultiQueryBody) -> Result<MultiQueryResponse>` |
| `batch_query` | `(body: BatchQueryBody) -> Result<BatchQueryResponse>` |

### Vectors

| Method | Signature |
|--------|-----------|
| `upsert` | `(collection: &str, vectors: Vec<VectorEntry>) -> Result<UpsertResponse>` |
| `delete` | `(collection: &str, ids: &[&str]) -> Result<DeleteResponse>` |

### Webhooks

| Method | Signature |
|--------|-----------|
| `create` | `(body: CreateWebhookBody) -> Result<CreateWebhookResponse>` |
| `list` | `() -> Result<WebhookListResponse>` |
| `get` | `(id: &str) -> Result<Webhook>` |
| `update` | `(id: &str, body: UpdateWebhookBody) -> Result<Webhook>` |
| `delete` | `(id: &str) -> Result<StatusResponse>` |
| `list_deliveries` | `(id: &str, options: Option<PaginationOptions>) -> Result<WebhookDeliveryListResponse>` |
| `test` | `(id: &str) -> Result<WebhookTestResponse>` |

### CollectionClient (Scoped Convenience)

Wraps all collection-scoped operations without requiring the collection name each time:

```rust
let col = client.collection("my-col");
col.upload(file, None).await?;
col.query(QueryBody { query: "hello".into(), ..Default::default() }).await?;
col.list_documents(None).await?;
col.stats().await?;
col.analytics().await?;
col.stream_events();
```

## File Input

```rust
pub enum FileInput {
    Path(PathBuf),
    PathWithName { path: PathBuf, name: String },
    Bytes { data: Vec<u8>, name: String },
    Stream { body: reqwest::Body, name: String },
}
```

Ergonomic `From` implementations:
- `&str`, `String`, `PathBuf`, `&Path` → `FileInput::Path`
- `(Vec<u8>, &str)` → `FileInput::Bytes`

Each variant converts to `reqwest::multipart::Part` at upload time via `into_multipart_part()`.

## Error Handling

```rust
pub enum BigRagError {
    BadRequest { message: String, status: u16 },
    Authentication { message: String },
    NotFound { message: String },
    Conflict { message: String },
    RateLimited,
    ServerError { message: String, status: u16 },
    Timeout(Duration),
    Connection(String),
    FileRead(std::io::Error),
    Serialization(serde_json::Error),
    Api { status: u16, message: String },
}
```

HTTP status code mapping:
- 400 → `BadRequest`
- 401/403 → `Authentication`
- 404 → `NotFound`
- 409 → `Conflict`
- 429 → `RateLimited`
- 500-599 → `ServerError`
- Other → `Api`

Error message extraction follows FastAPI's `{"detail": "..."}` format, with fallbacks to `{"error": {"message": "..."}}` and `{"message": "..."}`.

Helper methods: `status() -> Option<u16>`, `is_retryable() -> bool`.

## HTTP Transport

Internal `Transport` struct handles:

- **JSON requests**: `request<T>(method, path, opts) -> Result<T>`
- **Multipart requests**: `request_multipart<T>(path, form) -> Result<T>`
- **SSE streams**: `request_stream(path) -> Result<SseStream>`

### Retry Logic

- Retries on: 429, 5xx, timeouts, connection errors
- Does NOT retry: 4xx client errors, serialization errors, multipart/SSE requests
- Exponential backoff: 500ms → 1s → 2s → 4s (capped)
- Default max retries: 2

### Authentication

- `Authorization: Bearer <api_key>` header on all requests
- SSE endpoints also append `?token=<api_key>` query param

### User-Agent

`bigrag-rust/{version}` using `env!("CARGO_PKG_VERSION")`.

## SSE Streaming

`SseStream` implements `futures_core::Stream<Item = Result<ProgressEvent, BigRagError>>`.

Uses `pin-project-lite` for pin projection. Reads response body chunks, buffers partial lines, parses `data: {json}` lines, skips heartbeat comments (`: heartbeat`).

Users consume with `StreamExt` from `futures-util` or `tokio-stream`:

```rust
use futures_util::StreamExt;

let mut stream = client.documents().stream_progress("col", "doc-id");
while let Some(event) = stream.next().await {
    let event = event?;
    println!("[{}] {}%", event.step, event.progress);
}
```

## Testing Strategy

**Unit tests** with `wiremock`:
- Mock every endpoint, verify request path/method/headers/body
- Verify deserialization of all response types
- Test retry logic (mock 500 → 200 on retry)
- Test error mapping (mock 404 → `BigRagError::NotFound`)
- Test SSE parsing with mock event streams
- Test all `FileInput` conversions

**Examples** (runnable against live server):
- `basic_usage.rs`: Create collection, upload document, query
- `file_upload.rs`: Various `FileInput` patterns, batch upload

## Cargo.toml Metadata

```toml
[package]
name = "bigrag"
version = "0.1.0"
edition = "2021"
rust-version = "1.75"
description = "Rust client for bigRAG — a self-hostable RAG platform"
license = "MIT"
repository = "https://github.com/bigrag/bigrag"
documentation = "https://docs.rs/bigrag"
keywords = ["rag", "vector-search", "embeddings", "ai", "document-ingestion"]
categories = ["api-bindings", "web-programming::http-client"]
```

## Public Exports

```rust
// lib.rs
pub use client::{BigRag, BigRagBuilder, BigRagConfig, CollectionClient};
pub use error::BigRagError;
pub use files::FileInput;
pub use sse::SseStream;
pub use resources::{Collections, Documents, Queries, Vectors, Webhooks};
pub mod types;
```

All public types and methods have `///` doc comments. `#![warn(missing_docs)]` enforced.
