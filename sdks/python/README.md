# bigRAG Python SDK

Async Python client for the bigRAG API.

```bash
pip install bigrag
```

```python
import asyncio

from bigrag import BigRAG


async def main() -> None:
    async with BigRAG(api_key="bigrag_sk_...", base_url="http://localhost:4000") as client:
        doc = await client.documents.upload("docs", "/path/to/paper.pdf")
        result = await client.queries.query("docs", {"query": "What is RAG?"})
        print(doc["id"], result["total"])


asyncio.run(main())
```

The SDK is fully typed, ships `py.typed`, and uses CalVer releases like `2026.5.22`.

## Namespaces

- `client.collections` for collection CRUD, stats, realtime tokens, and event streams.
- `client.documents` for uploads, batch operations, chunks, elements, and status polling.
- `client.queries` for single, multi-collection, and batch retrieval queries.
- `client.vectors` for raw vector upsert and delete.
- `client.webhooks` for webhook management and delivery replay.
- `client.auth` for session login, setup, preferences, and identity.
- `client.admin` for users, API keys, access logs, audit logs, runtime settings, vector storage overview, admin realtime helpers, connector config, embedding presets, and MCP server keys.
- `client.realtime` for explicit WebSocket connect, subscribe, and unsubscribe control.
- `client.connectors.s3` for S3-compatible bucket-prefix sources and sync jobs.
- `client.evaluations` for golden-set retrieval evaluations.

## Authentication

API-key endpoints accept `api_key` or the `BIGRAG_API_KEY` environment variable.
Session-only admin endpoints can be used after calling `client.auth.login(...)` or
`client.auth.setup(...)`; the client keeps the session cookie in its underlying
`httpx.AsyncClient`.

## Versioning

Published artifacts use CalVer in the form `YYYY.M.D`.
