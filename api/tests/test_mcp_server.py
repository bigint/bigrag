from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from bigrag import mcp_server


class FakeMCP:
    instances = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.tools = {}
        self.runs = []
        FakeMCP.instances.append(self)

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator

    def run(self, *args, **kwargs) -> None:
        self.runs.append((args, kwargs))


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
    def __init__(self, responses=None, exc=None, **kwargs) -> None:
        self.responses = list(responses or [])
        self.exc = exc
        self.kwargs = kwargs
        self.requests = []
        self.base_url = httpx.URL(kwargs.get("base_url", "http://example.test"))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, path, params=None):
        self.requests.append(("GET", path, params, None))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)

    async def post(self, path, json=None):
        self.requests.append(("POST", path, None, json))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)


def test_mcp_status_and_scope_helpers() -> None:
    mcp_server._raise_for_status(FakeResponse(status_code=204))

    with pytest.raises(RuntimeError, match="upstream server error"):
        mcp_server._raise_for_status(FakeResponse(status_code=503))
    with pytest.raises(RuntimeError, match="bad"):
        mcp_server._raise_for_status(FakeResponse({"detail": "bad"}, status_code=400))
    with pytest.raises(RuntimeError, match="plain"):
        mcp_server._raise_for_status(
            FakeResponse(ValueError("no json"), status_code=404, text="plain")
        )

    assert "multi_collection_query" in mcp_server._unscoped_instructions()
    assert "docs" in mcp_server._scoped_instructions("docs")


def test_discover_scope_maps_auth_and_connection_errors() -> None:
    async def run() -> None:
        scoped = FakeClient([FakeResponse({"collection": "docs"})])
        assert await mcp_server._discover_scope(scoped) == "docs"

        unscoped = FakeClient([FakeResponse({"collection": ""})])
        assert await mcp_server._discover_scope(unscoped) is None

        rejected = FakeClient([FakeResponse(status_code=401)])
        with pytest.raises(RuntimeError, match="API key rejected"):
            await mcp_server._discover_scope(rejected)

        broken = FakeClient(exc=httpx.ConnectError("down"))
        with pytest.raises(RuntimeError, match="could not reach"):
            await mcp_server._discover_scope(broken)

    asyncio.run(run())


def test_create_unscoped_server_registers_and_executes_tools(monkeypatch) -> None:
    async def run() -> None:
        FakeMCP.instances.clear()
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
        monkeypatch.setattr(mcp_server, "FastMCP", FakeMCP)
        monkeypatch.setattr(mcp_server, "_make_client", lambda base_url, api_key: client)

        server = mcp_server.create_server("http://api", "key")

        assert server.kwargs["name"] == "bigrag"
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
        assert await server.tools["list_collections"](limit=5, offset=2) == {"collections": []}
        assert await server.tools["get_collection"]("docs") == {"name": "docs"}
        assert await server.tools["get_collection_stats"]("docs") == {"points": 3}
        assert await server.tools["query"](
            "docs",
            "hello",
            top_k=2,
            search_mode="hybrid",
            min_score=0.5,
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
                "search_mode": "hybrid",
                "rerank": True,
                "min_score": 0.5,
                "filters": {"tenant": "acme"},
            },
        )
        assert client.requests[5][2] == {"limit": 50, "offset": 0, "status": "ready"}

    asyncio.run(run())


def test_create_scoped_server_uses_pinned_collection(monkeypatch) -> None:
    async def run() -> None:
        client = FakeClient(
            [
                FakeResponse({"name": "docs"}),
                FakeResponse({"points": 1}),
                FakeResponse({"results": []}),
                FakeResponse({"documents": []}),
                FakeResponse({"id": "doc"}),
                FakeResponse({"chunks": []}),
            ]
        )
        monkeypatch.setattr(mcp_server, "FastMCP", FakeMCP)
        monkeypatch.setattr(mcp_server, "_make_client", lambda base_url, api_key: client)

        server = mcp_server.create_server("http://api", "key", collection="docs")

        assert server.kwargs["name"] == "bigrag-docs"
        assert sorted(server.tools) == [
            "get_collection",
            "get_collection_stats",
            "get_document",
            "get_document_chunks",
            "list_documents",
            "query",
        ]
        assert await server.tools["get_collection"]() == {"name": "docs"}
        assert await server.tools["get_collection_stats"]() == {"points": 1}
        assert await server.tools["query"]("hello") == {"results": []}
        assert await server.tools["list_documents"](status="failed") == {"documents": []}
        assert await server.tools["get_document"]("doc-id") == {"id": "doc"}
        assert await server.tools["get_document_chunks"]("doc-id") == {"chunks": []}

        assert client.requests[2][1] == "/v1/collections/docs/query"
        assert client.requests[3][2] == {"limit": 50, "offset": 0, "status": "failed"}

    asyncio.run(run())


def test_cli_probes_scope_and_runs_server(monkeypatch) -> None:
    async def fake_discover(client):
        assert client is fake_client
        return "docs"

    fake_client = FakeClient()
    server = FakeMCP(name="server")
    monkeypatch.setattr(mcp_server, "_make_client", lambda base_url, api_key: fake_client)
    monkeypatch.setattr(mcp_server, "_discover_scope", fake_discover)
    monkeypatch.setattr(mcp_server, "create_server", lambda base_url, api_key, collection: server)
    monkeypatch.setattr(
        mcp_server.argparse.ArgumentParser,
        "parse_args",
        lambda self: SimpleNamespace(
            base_url="http://api",
            api_key="key",
            transport="streamable-http",
            port=6101,
        ),
    )

    mcp_server.cli()

    assert server.runs == [((), {"transport": "streamable-http"})]


def test_cli_exits_when_probe_fails(monkeypatch, capsys) -> None:
    async def fail_discover(client):
        raise RuntimeError("bad key")

    monkeypatch.setattr(mcp_server, "_make_client", lambda base_url, api_key: FakeClient())
    monkeypatch.setattr(mcp_server, "_discover_scope", fail_discover)
    monkeypatch.setattr(
        mcp_server.argparse.ArgumentParser,
        "parse_args",
        lambda self: SimpleNamespace(
            base_url="http://api",
            api_key="key",
            transport="stdio",
            port=6101,
        ),
    )

    with pytest.raises(SystemExit):
        mcp_server.cli()

    assert "bad key" in capsys.readouterr().err
