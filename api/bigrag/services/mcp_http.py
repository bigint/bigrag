"""HTTP MCP endpoint mounted on the bigRAG FastAPI app.

Lets URL-only MCP clients (Claude's custom connector, Cursor remote
servers, etc.) connect without installing the ``bigrag-mcp`` Python
CLI. Point the client at ``https://bigrag.example.com/mcp?token=<key>``
and it gets the same toolset as the stdio server.

Auth: the incoming token is extracted from either
``?token=...`` or ``Authorization: Bearer ...``, stashed into a
contextvar, and re-used by the tool bodies for loopback ASGI calls to
the REST API. The REST layer enforces scope so a pinned key can't
escape its collection — the tools themselves are unscoped for display,
scope mismatches surface as tool errors.

Why loopback-via-ASGI and not a direct service call? Reuse: the REST
router already handles auth, rate limiting, scope enforcement, audit
logging, and idempotency. Duplicating that logic inside an MCP tool
would bitrot.
"""

from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Annotated, Any, Literal  # noqa: F401 — Any used in return type

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp

if TYPE_CHECKING:
    from fastapi import FastAPI

# Set by the middleware for the duration of a single request; read by
# tool bodies so they can propagate the caller's auth downstream.
_current_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "bigrag_mcp_http_token", default=None
)
_current_app: contextvars.ContextVar[FastAPI | None] = contextvars.ContextVar(
    "bigrag_mcp_http_app", default=None
)


class _TokenExtractMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):  # noqa: ANN001
        token: str | None = request.query_params.get("token")
        if not token:
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
    if app is None:  # pragma: no cover — defensive
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


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        payload = response.json()
        detail = payload.get("detail") or payload.get("error") or str(payload)
    except ValueError:
        detail = response.text or response.reason_phrase
    raise RuntimeError(f"bigRAG {response.status_code}: {detail}")


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
        # Serve at the mount root — the enclosing FastAPI app mounts this
        # at `/mcp`, so combined the endpoint is just `/mcp`.
        streamable_http_path="/",
        # The bigRAG FastAPI app fronts this endpoint behind whatever
        # hostname the operator uses. Auth is via bearer token, not Host
        # header, so DNS-rebinding protection is the wrong layer.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp.tool()
    async def list_collections(
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ) -> dict[str, Any]:
        """List document collections the current key can read."""
        async with _client() as c:
            r = await c.get("/v1/collections", params={"limit": limit, "offset": offset})
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def get_collection(
        name: Annotated[str, Field(description="Collection name")],
    ) -> dict[str, Any]:
        """Full metadata for a collection."""
        async with _client() as c:
            r = await c.get(f"/v1/collections/{name}")
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def get_collection_stats(
        name: Annotated[str, Field(description="Collection name")],
    ) -> dict[str, Any]:
        """Document/chunk/token counts and status breakdown."""
        async with _client() as c:
            r = await c.get(f"/v1/collections/{name}/stats")
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def query(
        collection: Annotated[str, Field(description="Collection name")],
        query: Annotated[str, Field(min_length=1, description="Natural-language query")],
        top_k: Annotated[int, Field(ge=1, le=100)] = 10,
        search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
        min_score: Annotated[
            float | None, Field(description="Drop results below this score")
        ] = None,
        rerank: Annotated[
            bool, Field(description="Run the collection's reranker")
        ] = False,
        filters: Annotated[
            dict[str, Any] | None, Field(description="Metadata filter")
        ] = None,
    ) -> dict[str, Any]:
        """Retrieve the top-k most relevant chunks from a collection."""
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
        async with _client() as c:
            r = await c.post(f"/v1/collections/{collection}/query", json=body)
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def multi_collection_query(
        collections: Annotated[list[str], Field(min_length=1, max_length=20)],
        query: Annotated[str, Field(min_length=1)],
        top_k: Annotated[int, Field(ge=1, le=100)] = 10,
        search_mode: Literal["semantic", "keyword", "hybrid"] = "semantic",
        min_score: Annotated[
            float | None, Field(description="Drop results below this score")
        ] = None,
        rerank: Annotated[
            bool, Field(description="Run each collection's reranker")
        ] = False,
        filters: Annotated[
            dict[str, Any] | None, Field(description="Metadata filter")
        ] = None,
    ) -> dict[str, Any]:
        """Search several collections in parallel."""
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
        async with _client() as c:
            r = await c.post("/v1/query", json=body)
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def list_documents(
        collection: Annotated[str, Field(description="Collection name")],
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
        status: Literal["pending", "processing", "ready", "failed"] | None = None,
    ) -> dict[str, Any]:
        """List documents in a collection."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            params["status"] = status
        async with _client() as c:
            r = await c.get(f"/v1/collections/{collection}/documents", params=params)
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def get_document(
        collection: Annotated[str, Field(description="Collection name")],
        document_id: Annotated[str, Field(description="Document UUID")],
    ) -> dict[str, Any]:
        """One document's metadata."""
        async with _client() as c:
            r = await c.get(f"/v1/collections/{collection}/documents/{document_id}")
            _raise_for_status(r)
            return r.json()

    @mcp.tool()
    async def get_document_chunks(
        collection: Annotated[str, Field(description="Collection name")],
        document_id: Annotated[str, Field(description="Document UUID")],
    ) -> dict[str, Any]:
        """Every chunk of a document in order."""
        async with _client() as c:
            r = await c.get(f"/v1/collections/{collection}/documents/{document_id}/chunks")
            _raise_for_status(r)
            return r.json()

    return mcp


def build_mcp_http_app(parent_app: FastAPI) -> tuple[ASGIApp, Any]:
    """Return ``(mcp_asgi_app, session_manager)``.

    * Mount ``mcp_asgi_app`` at ``/mcp`` on the parent FastAPI.
    * Enter ``session_manager.run()`` as an async context in the parent's
      lifespan — FastMCP's streamable-http transport uses a task group
      that must be started before any request is served.

    Each incoming request gets the caller's token stashed in a
    contextvar (via ``_TokenExtractMiddleware``) and the parent FastAPI
    bound as the ASGI target (via ``_ParentAppBinding``), so tool bodies
    can dispatch into the REST API without a network hop.
    """
    mcp = _build_server()
    http_app = mcp.streamable_http_app()

    class _ParentAppBinding(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):  # noqa: ANN001
            reset = _current_app.set(parent_app)
            try:
                return await call_next(request)
            finally:
                _current_app.reset(reset)

    http_app.add_middleware(_TokenExtractMiddleware)
    http_app.add_middleware(_ParentAppBinding)
    return http_app, mcp.session_manager
