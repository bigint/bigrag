# bigRAG Python SDK

Python client for the [bigRAG](https://github.com/yoginth/bigrag) RAG platform.

## Installation

```bash
pip install bigrag
```

## Quick Start

```python
from bigrag import BigRAG

client = BigRAG(api_key="your-api-key")

# Create a collection
client.create_collection("research", description="Research papers")

# Upload a document
client.upload_document("research", "paper.pdf")

# Query
results = client.query("research", "What are the main findings?", top_k=5)
for r in results.results:
    print(f"Score: {r.score:.3f} — {r.text[:100]}...")
```

## Async Usage

```python
import asyncio
from bigrag import AsyncBigRAG

async def main():
    async with AsyncBigRAG(api_key="your-api-key") as client:
        await client.create_collection("docs")
        await client.upload_document("docs", "manual.pdf")
        results = await client.query("docs", "How do I configure logging?")
        for r in results.results:
            print(f"{r.score:.3f}: {r.text[:80]}")

asyncio.run(main())
```

## Configuration

```python
client = BigRAG(
    api_key="your-key",                  # or set BIGRAG_API_KEY env var
    base_url="http://localhost:8080",
    timeout=120.0,
    max_retries=2,
)
```

## Collection Operations

```python
# List collections
collections = client.list_collections()

# Create with custom embedding model
client.create_collection(
    "multilingual",
    embedding_provider="cohere",
    embedding_model="embed-multilingual-v3.0",
    dimension=1024,
    chunk_size=1024,
)

# Get details
col = client.get_collection("research")
print(col.document_count, col.embedding_model)

# Delete
client.delete_collection("old_collection")
```

## Document Operations

```python
# Upload document (PDF, DOCX, PPTX, HTML, Markdown, images)
doc = client.upload_document("research", "paper.pdf", metadata={"author": "Alice"})

# List documents
docs = client.list_documents("research")
for d in docs.documents:
    print(f"{d.filename} — {d.status} ({d.chunk_count} chunks)")

# Reprocess a failed document
client.reprocess_document("research", doc.id)

# Delete
client.delete_document("research", doc.id)
```

## Query

```python
# Basic query
results = client.query("research", "What is RAG?", top_k=10)

# With minimum score filter
results = client.query("research", "deployment guide", min_score=0.5)

# With metadata filters
results = client.query("research", "findings", filters={"author": {"$eq": "Alice"}})
```

## Direct Vector Operations

```python
# Upsert pre-computed vectors
client.upsert_vectors("research", [
    {"id": "v1", "embedding": [0.1, 0.2, ...], "text": "hello world"},
])

# Delete vectors
client.delete_vectors("research", ["v1", "v2"])
```

## Error Handling

```python
from bigrag import BigRAGError, APIError, NotFoundError

try:
    client.query("nonexistent", "test")
except NotFoundError:
    print("Collection not found")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## License

MIT
