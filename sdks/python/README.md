# bigRAG Python SDK

Python client for the [bigRAG](https://github.com/yoginth/bigrag) vector database.

## Installation

```bash
pip install bigrag
```

## Quick Start

```python
from bigrag import BigRAG

client = BigRAG(api_key="your-api-key")

# Create a namespace and upsert vectors
ns = client.namespace("my-namespace")
ns.upsert(
    [
        {"id": 1, "vector": [0.1, 0.2, 0.3], "title": "First document"},
        {"id": 2, "vector": [0.4, 0.5, 0.6], "title": "Second document"},
    ],
    distance_metric="cosine_distance",
)

# Query
results = ns.query(
    rank_by=["vector", "ANN", [0.1, 0.2, 0.3]],
    top_k=10,
    include_attributes=True,
)
for row in results.rows:
    print(f"id={row.id} dist={row.dist} attrs={row.attributes}")
```

## Async Usage

```python
import asyncio
from bigrag import AsyncBigRAG

async def main():
    async with AsyncBigRAG(api_key="your-api-key") as client:
        ns = client.namespace("my-namespace")
        await ns.upsert(
            [{"id": 1, "vector": [0.1, 0.2, 0.3], "title": "hello"}],
            distance_metric="cosine_distance",
        )
        results = await ns.query(
            rank_by=["vector", "ANN", [0.1, 0.2, 0.3]],
            top_k=5,
        )
        print(results.rows)

asyncio.run(main())
```

## Configuration

```python
client = BigRAG(
    api_key="your-key",          # or set BIGRAG_API_KEY env var
    base_url="http://localhost:8080",
    timeout=60.0,
    max_retries=2,
)
```

## Namespace Operations

```python
ns = client.namespace("my-ns")

# Upsert rows
ns.upsert([{"id": 1, "vector": [0.1, 0.2], "title": "doc"}])

# Query with filters
results = ns.query(
    rank_by=["vector", "ANN", [0.1, 0.2]],
    top_k=10,
    filters=["category", "Eq", "science"],
    include_attributes=True,
)

# Delete by IDs
ns.delete([1, 2, 3])

# Delete by filter
ns.delete_by_filter(["category", "Eq", "spam"])

# Patch rows (partial update)
ns.patch([{"id": 1, "title": "updated title"}])

# Get metadata
meta = ns.metadata()
print(meta.approx_row_count)

# Schema operations
schema = ns.schema()
ns.update_schema({"title": "string", "score": "float"})

# Delete entire namespace
ns.delete_all()
```

## Listing Namespaces

```python
response = client.namespaces(prefix="prod-", page_size=50)
for ns_summary in response.namespaces:
    print(ns_summary.id)
```

## Error Handling

```python
from bigrag import BigRAGError, APIError, NotFoundError, RateLimitError

try:
    ns.query(rank_by=["vector", "ANN", [0.1, 0.2]], top_k=10)
except NotFoundError:
    print("Namespace not found")
except RateLimitError:
    print("Rate limited, slow down")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
except BigRAGError as e:
    print(f"Client error: {e.message}")
```

## License

Apache-2.0
