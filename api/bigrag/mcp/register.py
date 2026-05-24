from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
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
    call_list_collections,
    call_list_documents,
    call_multi_collection_query,
    call_query,
)

ClientProvider = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


def shared_client_provider(client: httpx.AsyncClient) -> ClientProvider:
    @asynccontextmanager
    async def provider() -> Any:
        yield client

    return provider


def register(mcp: FastMCP, client: ClientProvider, pinned: str | None = None) -> None:
    if pinned is None:
        _register_unscoped(mcp, client)
    else:
        _register_scoped(mcp, client, pinned)


def _register_unscoped(mcp: FastMCP, client: ClientProvider) -> None:
    @mcp.tool()
    async def list_collections(
        limit: Annotated[int, Field(ge=1, le=100, description="Max collections to return")] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_list_collections(c, limit, offset)

    @mcp.tool()
    async def get_collection(name: CollectionName) -> dict[str, Any]:
        async with client() as c:
            return await call_get_collection(c, name)

    @mcp.tool()
    async def get_collection_stats(name: CollectionName) -> dict[str, Any]:
        async with client() as c:
            return await call_get_collection_stats(c, name)

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
        skip_cache: Annotated[bool, Field(description="Bypass Redis query caches")] = False,
        filters: Annotated[
            dict[str, Any] | None,
            Field(description="Metadata filter, e.g. {'source': 'docs'}"),
        ] = None,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_query(
                c, collection, query, top_k, search_mode, min_score, rerank, skip_cache, filters
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
        skip_cache: Annotated[bool, Field(description="Bypass Redis query caches")] = False,
        filters: Annotated[dict[str, Any] | None, Field(description="Metadata filter")] = None,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_multi_collection_query(
                c, collections, query, top_k, search_mode, min_score, rerank, skip_cache, filters
            )

    @mcp.tool()
    async def list_documents(
        collection: CollectionName,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_list_documents(c, collection, limit, offset, status)

    @mcp.tool()
    async def get_document(
        collection: CollectionName,
        document_id: DocumentId,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_get_document(c, collection, document_id)

    @mcp.tool()
    async def get_document_chunks(
        collection: CollectionName,
        document_id: DocumentId,
        limit: Annotated[int, Field(ge=1, le=1000)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_get_document_chunks(c, collection, document_id, limit, offset)


def _register_scoped(mcp: FastMCP, client: ClientProvider, pinned: str) -> None:
    @mcp.tool()
    async def get_collection() -> dict[str, Any]:
        async with client() as c:
            return await call_get_collection(c, pinned)

    @mcp.tool()
    async def get_collection_stats() -> dict[str, Any]:
        async with client() as c:
            return await call_get_collection_stats(c, pinned)

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
        async with client() as c:
            return await call_query(
                c, pinned, query, top_k, search_mode, min_score, rerank, skip_cache, filters
            )

    @mcp.tool()
    async def list_documents(
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_list_documents(c, pinned, limit, offset, status)

    @mcp.tool()
    async def get_document(document_id: DocumentId) -> dict[str, Any]:
        async with client() as c:
            return await call_get_document(c, pinned, document_id)

    @mcp.tool()
    async def get_document_chunks(
        document_id: DocumentId,
        limit: Annotated[int, Field(ge=1, le=1000)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        async with client() as c:
            return await call_get_document_chunks(c, pinned, document_id, limit, offset)
