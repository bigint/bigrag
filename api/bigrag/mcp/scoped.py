from __future__ import annotations

from typing import Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .tools import (
    DocumentId,
    call_get_collection,
    call_get_collection_stats,
    call_get_document,
    call_get_document_chunks,
    call_list_documents,
    call_query,
)


def register(mcp: FastMCP, client: httpx.AsyncClient, pinned: str) -> None:
    @mcp.tool()
    async def get_collection() -> dict[str, Any]:
        return await call_get_collection(client, pinned)

    @mcp.tool()
    async def get_collection_stats() -> dict[str, Any]:
        return await call_get_collection_stats(client, pinned)

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
        skip_cache: Annotated[bool, Field(description="Bypass Redis query caches")] = False,
        filters: Annotated[
            dict[str, Any] | None,
            Field(description="Metadata filter, e.g. {'source': 'docs'}"),
        ] = None,
    ) -> dict[str, Any]:
        return await call_query(
            client, pinned, query, top_k, search_mode, min_score, rerank, skip_cache, filters
        )

    @mcp.tool()
    async def list_documents(
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        return await call_list_documents(client, pinned, limit, offset, status)

    @mcp.tool()
    async def get_document(document_id: DocumentId) -> dict[str, Any]:
        return await call_get_document(client, pinned, document_id)

    @mcp.tool()
    async def get_document_chunks(document_id: DocumentId) -> dict[str, Any]:
        return await call_get_document_chunks(client, pinned, document_id)
