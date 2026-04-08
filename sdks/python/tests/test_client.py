"""Tests for the bigRAG Python SDK."""

from __future__ import annotations

import json

import httpx
import pytest

from bigrag import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BigRAG,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(
    status: int = 200,
    body: dict | list | None = None,
    text: str = "",
) -> httpx.Response:
    content = json.dumps(body).encode() if body is not None else text.encode()
    return httpx.Response(status, content=content, headers={"content-type": "application/json"})


class MockTransport(httpx.AsyncBaseTransport):
    """Captures requests and returns pre-configured responses."""

    def __init__(self, responses: list[httpx.Response] | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self._responses = list(responses or [])
        self._index = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return _mock_response(200, {"status": "ok"})


def _make_client(
    responses: list[httpx.Response] | None = None,
    api_key: str = "test-key",
) -> tuple[BigRAG, MockTransport]:
    transport = MockTransport(responses)
    http_client = httpx.AsyncClient(transport=transport)
    client = BigRAG(api_key=api_key, http_client=http_client, max_retries=0)
    return client, transport


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        client = BigRAG(api_key="k")
        assert client.api_key == "k"
        assert client.base_url == "http://localhost:6100"
        assert client.timeout == 120.0
        assert client.max_retries == 2

    def test_custom_values(self):
        client = BigRAG(
            api_key="secret",
            base_url="https://api.example.com/",
            timeout=30.0,
            max_retries=5,
        )
        assert client.api_key == "secret"
        assert client.base_url == "https://api.example.com"  # trailing slash stripped
        assert client.timeout == 30.0
        assert client.max_retries == 5

    def test_resource_namespaces(self):
        client = BigRAG(api_key="k")
        assert client.collections is not None
        assert client.documents is not None
        assert client.queries is not None
        assert client.vectors is not None
        assert client.webhooks is not None


# ---------------------------------------------------------------------------
# Platform endpoints
# ---------------------------------------------------------------------------


class TestPlatformEndpoints:
    @pytest.mark.anyio
    async def test_health(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "version": "0.0.2"})]
        )
        result = await client.health()
        assert result["status"] == "ok"
        assert result["version"] == "0.0.2"
        assert transport.calls[0].method == "GET"
        assert str(transport.calls[0].url).endswith("/health")

    @pytest.mark.anyio
    async def test_readiness(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "version": "0.0.2", "postgres": True, "milvus": True, "redis": True})]
        )
        result = await client.readiness()
        assert result["postgres"] is True

    @pytest.mark.anyio
    async def test_get_stats(self):
        client, transport = _make_client(
            [_mock_response(200, {"collections": 3, "documents": {"total": 10}, "webhooks": 1, "queue": {}})]
        )
        result = await client.get_stats()
        assert result["collections"] == 3
        assert "Authorization" in transport.calls[0].headers


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class TestCollections:
    @pytest.mark.anyio
    async def test_list(self):
        client, transport = _make_client(
            [_mock_response(200, {"collections": [], "total": 0})]
        )
        result = await client.collections.list()
        assert result["total"] == 0
        assert str(transport.calls[0].url).endswith("/v1/collections")

    @pytest.mark.anyio
    async def test_list_with_params(self):
        client, transport = _make_client(
            [_mock_response(200, {"collections": [], "total": 0})]
        )
        await client.collections.list(name="test", limit=10, offset=5)
        url = str(transport.calls[0].url)
        assert "name=test" in url
        assert "limit=10" in url
        assert "offset=5" in url

    @pytest.mark.anyio
    async def test_create(self):
        body = {"name": "docs", "embedding_provider": "openai"}
        client, transport = _make_client(
            [_mock_response(201, {"id": "1", "name": "docs"})]
        )
        await client.collections.create(body)
        req = transport.calls[0]
        assert req.method == "POST"
        assert json.loads(req.content)["name"] == "docs"

    @pytest.mark.anyio
    async def test_get(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "1", "name": "docs"})]
        )
        result = await client.collections.get("docs")
        assert result["name"] == "docs"
        assert "%2F" not in str(transport.calls[0].url)  # no slashes

    @pytest.mark.anyio
    async def test_update(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "1", "description": "updated"})]
        )
        await client.collections.update("docs", {"description": "updated"})
        assert transport.calls[0].method == "PUT"

    @pytest.mark.anyio
    async def test_delete(self):
        client, transport = _make_client([_mock_response(204)])
        result = await client.collections.delete("docs")
        assert result["status"] == "ok"
        assert transport.calls[0].method == "DELETE"

    @pytest.mark.anyio
    async def test_stats(self):
        client, transport = _make_client(
            [_mock_response(200, {"collection": "docs", "document_count": 5})]
        )
        result = await client.collections.stats("docs")
        assert result["document_count"] == 5


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class TestDocuments:
    @pytest.mark.anyio
    async def test_list(self):
        client, transport = _make_client(
            [_mock_response(200, {"documents": [], "total": 0})]
        )
        result = await client.documents.list("docs")
        assert result["total"] == 0

    @pytest.mark.anyio
    async def test_get(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "abc", "filename": "test.pdf"})]
        )
        result = await client.documents.get("docs", "abc")
        assert result["id"] == "abc"

    @pytest.mark.anyio
    async def test_delete(self):
        client, transport = _make_client([_mock_response(204)])
        result = await client.documents.delete("docs", "abc")
        assert result["status"] == "ok"

    @pytest.mark.anyio
    async def test_get_file_url(self):
        client, _ = _make_client()
        url = client.documents.get_file_url("my col", "doc-123")
        assert "my%20col" in url
        assert "token=test-key" in url

    @pytest.mark.anyio
    async def test_get_file_url_no_key(self):
        client, _ = _make_client(api_key="")
        url = client.documents.get_file_url("docs", "abc")
        assert "token" not in url

    @pytest.mark.anyio
    async def test_batch_get_status(self):
        client, transport = _make_client(
            [_mock_response(200, {"documents": [], "total": 0})]
        )
        await client.documents.batch_get_status("docs", ["a", "b"])
        body = json.loads(transport.calls[0].content)
        assert body["document_ids"] == ["a", "b"]

    @pytest.mark.anyio
    async def test_reprocess(self):
        client, transport = _make_client([_mock_response(200, {"status": "ok"})])
        await client.documents.reprocess("docs", "abc")
        assert transport.calls[0].method == "POST"
        assert "/reprocess" in str(transport.calls[0].url)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestQueries:
    @pytest.mark.anyio
    async def test_query(self):
        client, transport = _make_client(
            [_mock_response(200, {"results": [], "query": "test", "collection": "docs", "total": 0})]
        )
        result = await client.queries.query("docs", {"query": "test"})
        assert result["total"] == 0
        body = json.loads(transport.calls[0].content)
        assert body["query"] == "test"

    @pytest.mark.anyio
    async def test_multi_query(self):
        client, transport = _make_client(
            [_mock_response(200, {"results": [], "query": "q", "collections": ["a"], "total": 0})]
        )
        await client.queries.multi_query({"query": "q", "collections": ["a"]})
        assert str(transport.calls[0].url).endswith("/v1/query")

    @pytest.mark.anyio
    async def test_batch_query(self):
        client, transport = _make_client(
            [_mock_response(200, {"results": []})]
        )
        await client.queries.batch_query({"queries": [{"collection": "a", "query": "q"}]})
        assert str(transport.calls[0].url).endswith("/v1/batch/query")


# ---------------------------------------------------------------------------
# Vectors
# ---------------------------------------------------------------------------


class TestVectors:
    @pytest.mark.anyio
    async def test_upsert(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "upserted": 2})]
        )
        vectors = [{"id": "v1", "embedding": [0.1, 0.2]}, {"id": "v2", "embedding": [0.3, 0.4]}]
        result = await client.vectors.upsert("docs", vectors)
        assert result["upserted"] == 2
        body = json.loads(transport.calls[0].content)
        assert len(body["vectors"]) == 2

    @pytest.mark.anyio
    async def test_delete(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "deleted": 1})]
        )
        result = await client.vectors.delete("docs", ["v1"])
        assert result["deleted"] == 1


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class TestWebhooks:
    @pytest.mark.anyio
    async def test_create(self):
        client, transport = _make_client(
            [_mock_response(201, {"id": "w1", "url": "https://example.com", "secret": "sec"})]
        )
        result = await client.webhooks.create({"url": "https://example.com", "events": ["document.ready"]})
        assert result["secret"] == "sec"
        assert "/v1/admin/webhooks" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_list(self):
        client, transport = _make_client(
            [_mock_response(200, {"webhooks": []})]
        )
        result = await client.webhooks.list()
        assert result["webhooks"] == []

    @pytest.mark.anyio
    async def test_test_webhook(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "status_code": 200, "error": None})]
        )
        result = await client.webhooks.test("w1")
        assert result["status_code"] == 200
        assert "/test" in str(transport.calls[0].url)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    @pytest.mark.anyio
    async def test_400(self):
        client, _ = _make_client([_mock_response(400, {"detail": "Bad request"})])
        with pytest.raises(BadRequestError, match="Bad request"):
            await client.health()

    @pytest.mark.anyio
    async def test_401(self):
        client, _ = _make_client([_mock_response(401, {"detail": "Unauthorized"})])
        with pytest.raises(AuthenticationError):
            await client.health()

    @pytest.mark.anyio
    async def test_404(self):
        client, _ = _make_client([_mock_response(404, {"detail": "Not found"})])
        with pytest.raises(NotFoundError):
            await client.collections.get("missing")

    @pytest.mark.anyio
    async def test_429(self):
        client, _ = _make_client([_mock_response(429, {"detail": "Rate limited"})])
        with pytest.raises(RateLimitError):
            await client.health()

    @pytest.mark.anyio
    async def test_500(self):
        client, _ = _make_client([_mock_response(500, {"detail": "Server error"})])
        with pytest.raises(InternalServerError):
            await client.health()

    @pytest.mark.anyio
    async def test_error_code_preserved(self):
        client, _ = _make_client(
            [_mock_response(400, {"detail": "oops", "error": {"code": "INVALID_NAME"}})]
        )
        with pytest.raises(BadRequestError) as exc_info:
            await client.health()
        assert exc_info.value.status == 400


# ---------------------------------------------------------------------------
# Auth headers
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.mark.anyio
    async def test_bearer_token(self):
        client, transport = _make_client(api_key="my-secret")
        await client.health()
        assert transport.calls[0].headers["authorization"] == "Bearer my-secret"

    @pytest.mark.anyio
    async def test_no_auth_header_without_key(self):
        client, transport = _make_client(api_key="")
        await client.health()
        assert "authorization" not in transport.calls[0].headers

    @pytest.mark.anyio
    async def test_user_agent(self):
        client, transport = _make_client()
        await client.health()
        assert "bigrag-python" in transport.calls[0].headers["user-agent"]


# ---------------------------------------------------------------------------
# CollectionClient (scoped)
# ---------------------------------------------------------------------------


class TestCollectionClient:
    @pytest.mark.anyio
    async def test_scoped_query(self):
        client, transport = _make_client(
            [_mock_response(200, {"results": [], "query": "q", "collection": "docs", "total": 0})]
        )
        col = client.collection("docs")
        result = await col.query({"query": "q"})
        assert result["collection"] == "docs"
        assert "/v1/collections/docs/query" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_stats(self):
        client, transport = _make_client(
            [_mock_response(200, {"collection": "docs", "document_count": 10})]
        )
        col = client.collection("docs")
        result = await col.stats()
        assert result["document_count"] == 10


# ---------------------------------------------------------------------------
# File input normalization
# ---------------------------------------------------------------------------


class TestFileInput:
    def test_path_string(self, tmp_path):
        p = tmp_path / "test.pdf"
        p.write_bytes(b"PDF content")
        from bigrag._files import normalize_file_input
        name, data = normalize_file_input(str(p))
        assert name == "test.pdf"
        assert data == b"PDF content"

    def test_bytes(self):
        from bigrag._files import normalize_file_input
        name, data = normalize_file_input(b"raw bytes")
        assert name == "document"
        assert data == b"raw bytes"

    def test_tuple(self):
        from bigrag._files import normalize_file_input
        name, data = normalize_file_input(("custom.txt", b"hello"))
        assert name == "custom.txt"
        assert data == b"hello"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    @pytest.mark.anyio
    async def test_async_context_manager(self):
        transport = MockTransport([_mock_response(200, {"status": "ok", "version": "0.0.2"})])
        http_client = httpx.AsyncClient(transport=transport)
        async with BigRAG(api_key="k", http_client=http_client) as client:
            result = await client.health()
            assert result["status"] == "ok"
