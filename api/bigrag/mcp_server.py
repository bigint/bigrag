"""bigRAG MCP server.

Exposes bigRAG as a Model Context Protocol server so clients like
Claude Desktop, Cursor, and any other MCP-aware runtime can discover
collections and query them as first-class tools.

The server is a thin client of the bigRAG HTTP API — it doesn't talk to
Postgres or Milvus directly. Point it at a running bigRAG instance with
``BIGRAG_URL`` and authenticate with ``BIGRAG_API_KEY``.

Usage::

    BIGRAG_URL=https://bigrag.example.com \\
    BIGRAG_API_KEY=bigrag_sk_... \\
    bigrag-mcp
"""

from __future__ import annotations

import argparse
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


def create_server(base_url: str, api_key: str | None) -> FastMCP:
    mcp = FastMCP(
        name="bigrag",
        instructions=(
            "bigRAG is a self-hosted RAG platform. Use `query` to retrieve "
            "the most relevant chunks from a document collection, "
            "`list_collections` to discover what's available, and "
            "`get_document` / `get_document_chunks` to inspect specific "
            "documents. For unfamiliar questions, start with `query` on a "
            "relevant collection — return the chunk text verbatim and cite "
            "the document_id."
        ),
    )
    client = _make_client(base_url, api_key)

    @mcp.tool()
    async def list_collections(
        limit: Annotated[int, Field(ge=1, le=100, description="Max collections to return")] = 50,
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
        """Fetch a collection's full metadata: embedding config, chunking,
        reranker, document count, and defaults."""
        r = await client.get(f"/v1/collections/{name}")
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
        r = await client.get(
            f"/v1/collections/{collection}/documents/{document_id}/chunks"
        )
        _raise_for_status(r)
        return r.json()

    return mcp


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="bigrag-mcp",
        description=(
            "bigRAG MCP server — expose a bigRAG instance over the Model Context Protocol."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIGRAG_URL", "http://localhost:6100"),
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

    server = create_server(args.base_url, args.api_key)
    if args.transport == "stdio":
        server.run()
    else:
        server.run(transport="streamable-http")


if __name__ == "__main__":
    cli()
