from __future__ import annotations

from typing import Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .tools import (
    CollectionName,
    DocumentId,
    call_get_collection,
    call_get_collection_stats,
    call_get_document,
    call_get_document_chunks,
    call_list_documents,
    call_query,
    raise_for_status,
)


def register(mcp: FastMCP, client: httpx.AsyncClient) -> None:
    @mcp.tool()
    async def list_collections(
        limit: Annotated[int, Field(ge=1, le=100, description="Max collections to return")] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        r = await client.get("/v1/collections", params={"limit": limit, "offset": offset})
        raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def get_collection(name: CollectionName) -> dict[str, Any]:
        return await call_get_collection(client, name)

    @mcp.tool()
    async def get_collection_stats(name: CollectionName) -> dict[str, Any]:
        return await call_get_collection_stats(client, name)

    @mcp.tool()
    async def query(
        collection: CollectionName,
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
        return await call_query(
            client, collection, query, top_k, search_mode, min_score, rerank, filters
        )

    @mcp.tool()
    async def multi_collection_query(
        collections: Annotated[
            list[CollectionName],
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
        raise_for_status(r)
        return r.json()

    @mcp.tool()
    async def list_documents(
        collection: CollectionName,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        return await call_list_documents(client, collection, limit, offset, status)

    @mcp.tool()
    async def get_document(
        collection: CollectionName,
        document_id: DocumentId,
    ) -> dict[str, Any]:
        return await call_get_document(client, collection, document_id)

    @mcp.tool()
    async def get_document_chunks(
        collection: CollectionName,
        document_id: DocumentId,
    ) -> dict[str, Any]:
        return await call_get_document_chunks(client, collection, document_id)
