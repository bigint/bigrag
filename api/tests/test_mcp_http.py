from __future__ import annotations

import asyncio

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from bigrag.services import mcp_http


class FakeMCP:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.tools = {}
        self.session_manager = object()
        self.http_app = Starlette()

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator

    def streamable_http_app(self):
        return self.http_app


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text="") -> None:
        self.payload = payload if payload is not None else {"ok": True}
        self.status_code = status_code
        self.text = text
        self.reason_phrase = "Reason"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeClient:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, path, params=None):
        self.requests.append(("GET", path, params, None))
        return self.responses.pop(0)

    async def post(self, path, json=None):
        self.requests.append(("POST", path, None, json))
        return self.responses.pop(0)


def test_mcp_http_status_and_client_context(monkeypatch) -> None:
    mcp_http._raise_for_status(FakeResponse(status_code=200))

    with pytest.raises(RuntimeError, match="upstream server error"):
        mcp_http._raise_for_status(FakeResponse(status_code=500))
    with pytest.raises(RuntimeError, match="bad"):
        mcp_http._raise_for_status(FakeResponse({"error": "bad"}, status_code=400))
    with pytest.raises(RuntimeError, match="plain"):
        mcp_http._raise_for_status(
            FakeResponse(ValueError("no json"), status_code=404, text="plain")
        )

    app = Starlette()
    token_reset = mcp_http._current_token.set("key")
    app_reset = mcp_http._current_app.set(app)
    try:
        client = mcp_http._client()
        assert client.headers["Authorization"] == "Bearer key"
        assert isinstance(client._transport, httpx.ASGITransport)
    finally:
        asyncio.run(client.aclose())
        mcp_http._current_app.reset(app_reset)
        mcp_http._current_token.reset(token_reset)


def test_mcp_http_tools_proxy_expected_requests(monkeypatch) -> None:
    async def run() -> None:
        fake_mcp = FakeMCP(name="bigrag")
        client = FakeClient(
            [
                FakeResponse({"collections": []}),
                FakeResponse({"name": "docs"}),
                FakeResponse({"points": 3}),
                FakeResponse({"results": []}),
                FakeResponse({"results": ["multi"]}),
                FakeResponse({"documents": []}),
                FakeResponse({"id": "doc"}),
                FakeResponse({"chunks": []}),
            ]
        )
        monkeypatch.setattr(mcp_http, "FastMCP", lambda **kwargs: fake_mcp)
        monkeypatch.setattr(mcp_http, "_client", lambda: client)

        server = mcp_http._build_server()

        assert server is fake_mcp
        assert sorted(server.tools) == [
            "get_collection",
            "get_collection_stats",
            "get_document",
            "get_document_chunks",
            "list_collections",
            "list_documents",
            "multi_collection_query",
            "query",
        ]
        assert await server.tools["list_collections"](limit=5, offset=1) == {"collections": []}
        assert await server.tools["get_collection"]("docs") == {"name": "docs"}
        assert await server.tools["get_collection_stats"]("docs") == {"points": 3}
        assert await server.tools["query"](
            "docs",
            "hello",
            top_k=2,
            search_mode="keyword",
            min_score=0.2,
            rerank=True,
            filters={"tenant": "acme"},
        ) == {"results": []}
        assert await server.tools["multi_collection_query"](
            ["docs"],
            "hello",
            top_k=2,
            search_mode="semantic",
            min_score=0.1,
            rerank=False,
            filters={"tenant": "acme"},
        ) == {"results": ["multi"]}
        assert await server.tools["list_documents"]("docs", status="ready") == {"documents": []}
        assert await server.tools["get_document"]("docs", "doc-id") == {"id": "doc"}
        assert await server.tools["get_document_chunks"]("docs", "doc-id") == {"chunks": []}

        assert client.requests[3] == (
            "POST",
            "/v1/collections/docs/query",
            None,
            {
                "query": "hello",
                "top_k": 2,
                "search_mode": "keyword",
                "rerank": True,
                "min_score": 0.2,
                "filters": {"tenant": "acme"},
            },
        )
        assert client.requests[5][2] == {"limit": 50, "offset": 0, "status": "ready"}

    asyncio.run(run())


def test_mcp_http_binding_middlewares_set_context(monkeypatch) -> None:
    async def run() -> None:
        fake_mcp = FakeMCP(name="bigrag")
        parent = Starlette()
        monkeypatch.setattr(mcp_http, "_build_server", lambda: fake_mcp)

        http_app, manager = mcp_http.build_mcp_http_app(parent)

        assert http_app is fake_mcp.http_app
        assert manager is fake_mcp.session_manager

        token_seen = []
        app_seen = []
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"authorization", b"Bearer secret")],
            },
            receive=lambda: None,
        )

        async def call_next(_request):
            token_seen.append(mcp_http._current_token.get())
            app_seen.append(mcp_http._current_app.get())
            return Response("ok")

        token_middleware = next(
            middleware
            for middleware in fake_mcp.http_app.user_middleware
            if "Token" in middleware.cls.__name__
        ).cls(fake_mcp.http_app)
        parent_middleware = next(
            middleware
            for middleware in fake_mcp.http_app.user_middleware
            if "Parent" in middleware.cls.__name__
        ).cls(fake_mcp.http_app)

        await parent_middleware.dispatch(
            request,
            lambda req: token_middleware.dispatch(req, call_next),
        )

        assert token_seen == ["secret"]
        assert app_seen == [parent]

    asyncio.run(run())
