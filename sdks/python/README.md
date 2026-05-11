# rag.computer Python SDK

Async Python client for the rag.computer API.

```bash
pip install rag-computer
```

```python
import asyncio

from rag_computer import RagComputer


async def main() -> None:
    async with RagComputer(api_key="ragc_sk_...", base_url="http://localhost:4000") as client:
        doc = await client.documents.upload("docs", "/path/to/paper.pdf")
        result = await client.queries.query("docs", {"query": "What is RAG?"})
        print(doc["id"], result["total"])


asyncio.run(main())
```

The SDK is fully typed, ships `py.typed`, and uses CalVer releases like `2026.5.7`.

## Namespaces

- `client.collections` for collection CRUD, stats, re-embedding, and event streams.
- `client.documents` for uploads, batch operations, file URLs, and status polling.
- `client.queries` for single, multi-collection, and batch retrieval queries.
- `client.vectors` for raw vector upsert and delete.
- `client.webhooks` for webhook management and delivery replay.
- `client.auth` for session login, setup, preferences, and identity.
- `client.admin` for users, API keys, access logs, audit logs, connector config, embedding presets, and MCP server keys.
- `client.connectors.google` for Google Drive account, file browsing, sources, and sync jobs.
- `client.evaluations` for golden-set retrieval evaluations.

## Authentication

API-key endpoints accept `api_key` or the `RAG_COMPUTER_API_KEY` environment variable.
Session-only admin endpoints can be used after calling `client.auth.login(...)` or
`client.auth.setup(...)`; the client keeps the session cookie in its underlying
`httpx.AsyncClient`.

## Versioning

Published artifacts use CalVer in the form `YYYY.M.D`.
