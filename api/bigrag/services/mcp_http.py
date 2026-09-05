from __future__ import annotations

import contextvars
from typing import TYPE_CHECKING, Any

import httpx
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import ASGIApp

from bigrag.mcp.register import register

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


def _build_server() -> MCPServer:
    mcp = MCPServer(
        name="bigrag",
        instructions=(
            "bigRAG retrieval tools. Use `query` to pull top-k chunks from a "
            "collection, `list_collections` / `get_collection_stats` to "
            "discover what's available, and `multi_collection_query` when the "
            "target is unknown. If the configured API key is pinned to a "
            "single collection, cross-collection tools return 403."
        ),
    )
    register(mcp, _client)
    return mcp


def build_mcp_http_app(parent_app: FastAPI) -> tuple[ASGIApp, Any]:
    mcp = _build_server()
    http_app = mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

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
