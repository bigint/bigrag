from __future__ import annotations

from typing import Annotated, Any

import httpx
from pydantic import Field

CollectionName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$",
        description="Collection name",
    ),
]
DocumentId = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        description="Document UUID",
    ),
]


def make_client(base_url: str, api_key: str | None) -> httpx.AsyncClient:
    headers = {"User-Agent": "bigrag-mcp/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=60)


def raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    if response.status_code >= 500:
        raise RuntimeError(f"bigRAG {response.status_code}: upstream server error")
    try:
        payload = response.json()
        detail = payload.get("detail") or payload.get("error") or str(payload)
    except ValueError:
        detail = response.text or response.reason_phrase
    raise RuntimeError(f"bigRAG {response.status_code}: {detail}")


async def discover_scope(client: httpx.AsyncClient) -> str | None:
    try:
        r = await client.get("/v1/auth/whoami")
    except httpx.HTTPError as e:
        raise RuntimeError(f"bigrag-mcp: could not reach bigRAG at {client.base_url!s}: {e}") from e
    if r.status_code == 401:
        raise RuntimeError("bigrag-mcp: API key rejected (401). Check BIGRAG_API_KEY.")
    raise_for_status(r)
    body = r.json()
    collection = body.get("collection")
    return collection if isinstance(collection, str) and collection else None


def unscoped_instructions() -> str:
    return (
        "bigRAG is a self-hosted RAG platform. Use `query` to retrieve the most "
        "relevant chunks from a document collection, `list_collections` / "
        "`get_collection_stats` to discover what's available, and "
        "`multi_collection_query` when the right collection is unknown. "
        "For unfamiliar questions, start with `query` on a relevant collection — "
        "return the chunk text verbatim and cite the document_id."
    )


def scoped_instructions(collection: str) -> str:
    return (
        f"bigRAG is a self-hosted RAG platform, scoped to the `{collection}` "
        "collection. Use `query` to retrieve the most relevant chunks for a "
        "question, and `get_document` / `get_document_chunks` to inspect "
        "specific documents. Return chunk text verbatim and cite the "
        "document_id."
    )


async def call_query(
    client: httpx.AsyncClient,
    collection: str,
    query: str,
    top_k: int,
    search_mode: str,
    min_score: float | None,
    rerank: bool,
    skip_cache: bool,
    filters: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "search_mode": search_mode,
        "rerank": rerank,
        "skip_cache": skip_cache,
    }
    if min_score is not None:
        body["min_score"] = min_score
    if filters is not None:
        body["filters"] = filters
    r = await client.post(f"/v1/collections/{collection}/query", json=body)
    raise_for_status(r)
    return r.json()


async def call_get_collection(client: httpx.AsyncClient, name: str) -> dict[str, Any]:
    r = await client.get(f"/v1/collections/{name}")
    raise_for_status(r)
    return r.json()


async def call_get_collection_stats(client: httpx.AsyncClient, name: str) -> dict[str, Any]:
    r = await client.get(f"/v1/collections/{name}/stats")
    raise_for_status(r)
    return r.json()


async def call_list_documents(
    client: httpx.AsyncClient,
    collection: str,
    limit: int,
    offset: int,
    status: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status is not None:
        params["status"] = status
    r = await client.get(f"/v1/collections/{collection}/documents", params=params)
    raise_for_status(r)
    return r.json()


async def call_get_document(
    client: httpx.AsyncClient,
    collection: str,
    document_id: str,
) -> dict[str, Any]:
    r = await client.get(f"/v1/collections/{collection}/documents/{document_id}")
    raise_for_status(r)
    return r.json()


async def call_get_document_chunks(
    client: httpx.AsyncClient,
    collection: str,
    document_id: str,
) -> dict[str, Any]:
    r = await client.get(f"/v1/collections/{collection}/documents/{document_id}/chunks")
    raise_for_status(r)
    return r.json()
