# Bigrag Architecture

Bigrag is a self-hostable retrieval-augmented-generation platform.
This document summarises the architecture used in the fixtures.

## API Layer

The API is a FastAPI app split into ~25 routers (auth, collections,
documents, query, chat, webhooks, admin). Every mutating endpoint runs
through CSRF, scope, and audit middleware.

## Ingestion Pipeline

1. Upload arrives at `/v1/collections/{name}/documents`
2. Conversion service (Docling) extracts text from PDF/DOCX/HTML/PNG
3. Chunker splits the document by `chunk_strategy`
4. Embedding worker batches chunks and embeds via the configured provider
5. Vectors and payloads are upserted into Turbopuffer

## Retrieval

Queries are embedded with the same model, then run as a hybrid
semantic + keyword search. A Redis cache shortcircuits hot queries.

```python
from bigrag import BigragClient
client = BigragClient(base_url="http://localhost:4000", api_key="bigrag_sk_...")
hits = await client.query(collection="docs", text="who founded Acme?", top_k=5)
```

## Operational notes

Each collection picks its own embedding provider, chunk size, and vector
store. Backups are uploaded to an S3-compatible bucket.
