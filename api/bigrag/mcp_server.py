"""bigRAG MCP server.

Exposes bigRAG as a Model Context Protocol server so clients like
Claude Desktop, Cursor, and any other MCP-aware runtime can discover
collections and query them as first-class tools.

The server is a thin client of the bigRAG HTTP API — it doesn't talk to
Postgres or Milvus directly. Point it at a running bigRAG instance with
``BIGRAG_URL`` and authenticate with ``BIGRAG_API_KEY``.

Scope is discovered from the API key itself via ``GET /v1/auth/whoami``
at startup:

* Full-workspace keys → all 8 tools, cross-collection ones included.
* Collection-pinned keys → the 6 scoped tools with the collection
  argument pre-bound, no cross-collection tools visible.

Usage::

    BIGRAG_URL=https://bigrag.example.com \\
    BIGRAG_API_KEY=bigrag_sk_... \\
    bigrag-mcp
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field


def _make_client(base_url: str, api_key: str | None) -> httpx.AsyncClient:
    headers = {"User-Agent": "bigrag-mcp/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=60)


def _raise_for_status(response: httpx.Response) -> None:
    """Surface HTTP errors as tool errors with the server's detail message."""
    if response.is_success:
        return
    try:
        payload = response.json()
        detail = payload.get("detail") or payload.get("error") or str(payload)
    except ValueError:
        detail = response.text or response.reason_phrase
    raise RuntimeError(f"bigRAG {response.status_code}: {detail}")


async def _discover_scope(client: httpx.AsyncClient) -> str | None:
    """Call /v1/auth/whoami. Returns the collection the key is pinned
    to, or None for full-workspace keys. Raises if the key is invalid."""
    try:
        r = await client.get("/v1/auth/whoami")
    except httpx.HTTPError as e:
        raise RuntimeError(f"bigrag-mcp: could not reach bigRAG at {client.base_url!s}: {e}") from e
    if r.status_code == 401:
        raise RuntimeError("bigrag-mcp: API key rejected (401). Check BIGRAG_API_KEY.")
    _raise_for_status(r)
    body = r.json()
    collection = body.get("collection")
    return collection if isinstance(collection, str) and collection else None


def _unscoped_instructions() -> str:
    return (
        "bigRAG is a self-hosted RAG platform. Use `query` to retrieve the most "
        "relevant chunks from a document collection, `list_collections` / "
        "`get_collection_stats` to discover what's available, and "
        "`multi_collection_query` when the right collection is unknown. "
        "For unfamiliar questions, start with `query` on a relevant collection — "
        "return the chunk text verbatim and cite the document_id."
    )


def _scoped_instructions(collection: str) -> str:
    return (
        f"bigRAG is a self-hosted RAG platform, scoped to the `{collection}` "
        "collection. Use `query` to retrieve the most relevant chunks for a "
        "question, and `get_document` / `get_document_chunks` to inspect "
        "specific documents. Return chunk text verbatim and cite the "
        "document_id."
    )


def create_server(
    base_url: str,
    api_key: str | None,
    collection: str | None = None,
) -> FastMCP:
    """Build an MCP server.

    When ``collection`` is set, tools that normally take a collection arg are
    pre-bound to it and the cross-collection tools (`list_collections`,
    `multi_collection_query`) are omitted.
    """
    mcp = FastMCP(
        name=f"bigrag-{collection}" if collection else "bigrag",
        instructions=_scoped_instructions(collection) if collection else _unscoped_instructions(),
    )
    client = _make_client(base_url, api_key)

    async def _query(
        collection: str,
        query: str,
        top_k: int,
        search_mode: str,
        min_score: float | None,
        rerank: bool,
        filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "search_mode": search_mode,
            "rerank": rerank,
        }
        if min_score is not None:
            body["min_score"] = min_score
        if filters is not None:
            body["filters"] = filters
        r = await client.post(f"/v1/collections/{collection}/query", json=body)
        _raise_for_status(r)
        return r.json()

    if collection is None:

        @mcp.tool()
        async def list_collections(
            limit: Annotated[
                int, Field(ge=1, le=100, description="Max collections to return")
            ] = 50,
            offset: Annotated[int, Field(ge=0)] = 0,
        ) -> dict[str, Any]:
            """List document collections visible to the current API key."""
            r = await client.get("/v1/collections", params={"limit": limit, "offset": offset})
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def get_collection(
            name: Annotated[str, Field(description="Collection name")],
        ) -> dict[str, Any]:
            """Fetch a collection's full metadata."""
            r = await client.get(f"/v1/collections/{name}")
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def get_collection_stats(
            name: Annotated[str, Field(description="Collection name")],
        ) -> dict[str, Any]:
            """Return document count, chunk count, total tokens/bytes, and a
            status breakdown for a collection. Cheap pre-flight before a
            `query` to decide whether a collection is worth searching."""
            r = await client.get(f"/v1/collections/{name}/stats")
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def query(
            collection: Annotated[str, Field(description="Collection name to search")],
            query: Annotated[str, Field(min_length=1, description="Natural-language query")],
            top_k: Annotated[int, Field(ge=1, le=100)] = 10,
            search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
            min_score: Annotated[
                float | None, Field(description="Drop results below this score (0–1)")
            ] = None,
            rerank: Annotated[
                bool, Field(description="Run the collection's configured reranker")
            ] = False,
            filters: Annotated[
                dict[str, Any] | None,
                Field(description="Metadata filter, e.g. {'source': 'docs'}"),
            ] = None,
        ) -> dict[str, Any]:
            """Retrieve the top-k most relevant chunks from a collection.

            Returns chunks with scores, the document_id they came from, and
            any metadata attached at upload time. Cite document_id in your
            answer so the user can trace it back.
            """
            return await _query(collection, query, top_k, search_mode, min_score, rerank, filters)

        @mcp.tool()
        async def multi_collection_query(
            collections: Annotated[
                list[str],
                Field(
                    min_length=1,
                    max_length=20,
                    description="Collections to search in parallel",
                ),
            ],
            query: Annotated[str, Field(min_length=1, description="Natural-language query")],
            top_k: Annotated[int, Field(ge=1, le=100)] = 10,
            search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
            min_score: Annotated[
                float | None, Field(description="Drop results below this score")
            ] = None,
            rerank: Annotated[bool, Field(description="Run each collection's reranker")] = False,
            filters: Annotated[dict[str, Any] | None, Field(description="Metadata filter")] = None,
        ) -> dict[str, Any]:
            """Search several collections in parallel when you don't know
            which one has the answer. Merges and scores results across them.
            Prefer over calling `query` in a loop."""
            body: dict[str, Any] = {
                "collections": collections,
                "query": query,
                "top_k": top_k,
                "search_mode": search_mode,
                "rerank": rerank,
            }
            if min_score is not None:
                body["min_score"] = min_score
            if filters is not None:
                body["filters"] = filters
            r = await client.post("/v1/query", json=body)
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def list_documents(
            collection: Annotated[str, Field(description="Collection name")],
            limit: Annotated[int, Field(ge=1, le=100)] = 50,
            offset: Annotated[int, Field(ge=0)] = 0,
            status: Literal["pending", "processing", "ready", "failed"] | None = None,
        ) -> dict[str, Any]:
            """List documents in a collection, optionally filtered by processing status."""
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if status is not None:
                params["status"] = status
            r = await client.get(f"/v1/collections/{collection}/documents", params=params)
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def get_document(
            collection: Annotated[str, Field(description="Collection name")],
            document_id: Annotated[str, Field(description="Document UUID")],
        ) -> dict[str, Any]:
            """Fetch a single document's metadata (filename, size, status, chunks)."""
            r = await client.get(f"/v1/collections/{collection}/documents/{document_id}")
            _raise_for_status(r)
            return r.json()

        @mcp.tool()
        async def get_document_chunks(
            collection: Annotated[str, Field(description="Collection name")],
            document_id: Annotated[str, Field(description="Document UUID")],
        ) -> dict[str, Any]:
            """Return every chunk of a document in order, with its text and metadata."""
            r = await client.get(f"/v1/collections/{collection}/documents/{document_id}/chunks")
            _raise_for_status(r)
            return r.json()

        return mcp

    pinned = collection

    @mcp.tool()
    async def get_collection() -> dict[str, Any]:
        """Fetch the pinned collection's metadata."""
        r = await client.get(f"/v1/collections/{pinned}")
        _raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def get_collection_stats() -> dict[str, Any]:
        """Document count, chunk count, total tokens/bytes, and status
        breakdown for the pinned collection."""
        r = await client.get(f"/v1/collections/{pinned}/stats")
        _raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def query(
        query: Annotated[str, Field(min_length=1, description="Natural-language query")],
        top_k: Annotated[int, Field(ge=1, le=100)] = 10,
        search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
        min_score: Annotated[
            float | None, Field(description="Drop results below this score (0–1)")
        ] = None,
        rerank: Annotated[
            bool, Field(description="Run the collection's configured reranker")
        ] = False,
        filters: Annotated[
            dict[str, Any] | None,
            Field(description="Metadata filter, e.g. {'source': 'docs'}"),
        ] = None,
    ) -> dict[str, Any]:
        """Retrieve the top-k most relevant chunks from the pinned collection."""
        return await _query(pinned, query, top_k, search_mode, min_score, rerank, filters)

    @mcp.tool()
    async def list_documents(
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        """List documents in the pinned collection, optionally filtered by processing status."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        r = await client.get(f"/v1/collections/{pinned}/documents", params=params)
        _raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def get_document(
        document_id: Annotated[str, Field(description="Document UUID")],
    ) -> dict[str, Any]:
        """Fetch a single document's metadata from the pinned collection."""
        r = await client.get(f"/v1/collections/{pinned}/documents/{document_id}")
        _raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def get_document_chunks(
        document_id: Annotated[str, Field(description="Document UUID")],
    ) -> dict[str, Any]:
        """Return every chunk of a document in order (pinned collection)."""
        r = await client.get(f"/v1/collections/{pinned}/documents/{document_id}/chunks")
        _raise_for_status(r)
        return r.json()

    return mcp


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="bigrag-mcp",
        description=(
            "bigRAG MCP server — expose a bigRAG instance over the Model Context Protocol. "
            "The toolset is scoped automatically from the API key: collection-pinned keys "
            "get a collection-scoped server."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIGRAG_URL", "http://localhost:4000"),
        help="bigRAG server URL (env: BIGRAG_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("BIGRAG_API_KEY"),
        help="bigRAG API key (env: BIGRAG_API_KEY)",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "streamable-http"),
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6101,
        help="Port for streamable-http transport (default: 6101)",
    )
    args = parser.parse_args()

    if not args.api_key:
        print(  # noqa: T201 — user-facing CLI warning on stderr
            "bigrag-mcp: warning — no API key set (env BIGRAG_API_KEY or --api-key). "
            "Requests will be unauthenticated and will fail on protected endpoints.",
            file=sys.stderr,
        )
        collection: str | None = None
    else:

        async def _probe() -> str | None:
            async with _make_client(args.base_url, args.api_key) as c:
                return await _discover_scope(c)

        try:
            collection = asyncio.run(_probe())
        except RuntimeError as e:
            print(f"bigrag-mcp: {e}", file=sys.stderr)  # noqa: T201
            sys.exit(1)

    server = create_server(args.base_url, args.api_key, collection)
    if args.transport == "stdio":
        server.run()
    else:
        server.run(transport="streamable-http")


if __name__ == "__main__":
    cli()
