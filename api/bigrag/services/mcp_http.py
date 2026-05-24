from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Annotated, Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp

from bigrag.mcp.tools import (
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

if TYPE_CHECKING:
    from fastapi import FastAPI

_current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "bigrag_mcp_http_token", default=None
)
_current_app: contextvars.ContextVar[FastAPI | None] = contextvars.ContextVar(
    "bigrag_mcp_http_app", default=None
)


class _TokenExtractMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        token: str | None = None
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        tok_reset = _current_token.set(token)
        try:
            return await call_next(request)
        finally:
            _current_token.reset(tok_reset)


def _client() -> httpx.AsyncClient:
    app = _current_app.get()
    if app is None:  # pragma: no cover
        raise RuntimeError("bigrag mcp_http: app context not set")
    token = _current_token.get()
    headers: dict[str, str] = {"User-Agent": "bigrag-mcp-http/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://bigrag.internal",
        headers=headers,
        timeout=60,
    )


def _build_server() -> FastMCP:
    mcp = FastMCP(
        name="bigrag",
        instructions=(
            "bigRAG retrieval tools. Use `query` to pull top-k chunks from a "
            "collection, `list_collections` / `get_collection_stats` to "
            "discover what's available, and `multi_collection_query` when the "
            "target is unknown. If the configured API key is pinned to a "
            "single collection, cross-collection tools return 403."
        ),
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp.tool()
    async def list_collections(
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        async with _client() as c:
            return await call_list_collections(c, limit, offset)

    @mcp.tool()
    async def get_collection(name: CollectionName) -> dict[str, Any]:
        async with _client() as c:
            return await call_get_collection(c, name)

    @mcp.tool()
    async def get_collection_stats(name: CollectionName) -> dict[str, Any]:
        async with _client() as c:
            return await call_get_collection_stats(c, name)

    @mcp.tool()
    async def query(
        collection: CollectionName,
        query: Annotated[str, Field(min_length=1, description="Natural-language query")],
        top_k: Annotated[int, Field(ge=1, le=100)] = 10,
        search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
        min_score: Annotated[
            float | None, Field(description="Drop results below this score")
        ] = None,
        rerank: Annotated[bool, Field(description="Run the collection's reranker")] = False,
        skip_cache: Annotated[bool, Field(description="Bypass Redis query caches")] = False,
        filters: Annotated[dict[str, Any] | None, Field(description="Metadata filter")] = None,
    ) -> dict[str, Any]:
        async with _client() as c:
            return await call_query(
                c, collection, query, top_k, search_mode, min_score, rerank, skip_cache, filters
            )

    @mcp.tool()
    async def multi_collection_query(
        collections: Annotated[list[CollectionName], Field(min_length=1, max_length=20)],
        query: Annotated[str, Field(min_length=1)],
        top_k: Annotated[int, Field(ge=1, le=100)] = 10,
        search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
        min_score: Annotated[
            float | None, Field(description="Drop results below this score")
        ] = None,
        rerank: Annotated[bool, Field(description="Run each collection's reranker")] = False,
        skip_cache: Annotated[bool, Field(description="Bypass Redis query caches")] = False,
        filters: Annotated[dict[str, Any] | None, Field(description="Metadata filter")] = None,
    ) -> dict[str, Any]:
        async with _client() as c:
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
        async with _client() as c:
            return await call_list_documents(c, collection, limit, offset, status)

    @mcp.tool()
    async def get_document(
        collection: CollectionName,
        document_id: DocumentId,
    ) -> dict[str, Any]:
        async with _client() as c:
            return await call_get_document(c, collection, document_id)

    @mcp.tool()
    async def get_document_chunks(
        collection: CollectionName,
        document_id: DocumentId,
    ) -> dict[str, Any]:
        async with _client() as c:
            return await call_get_document_chunks(c, collection, document_id)

    return mcp


def build_mcp_http_app(parent_app: FastAPI) -> tuple[ASGIApp, Any]:
    mcp = _build_server()
    http_app = mcp.streamable_http_app()

    class _ParentAppBinding(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            reset = _current_app.set(parent_app)
            try:
                return await call_next(request)
            finally:
                _current_app.reset(reset)

    http_app.add_middleware(_TokenExtractMiddleware)
    http_app.add_middleware(_ParentAppBinding)
    return http_app, mcp.session_manager
