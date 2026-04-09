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
        # Read streaming content so it can be inspected later via req.content
        await request.aread()
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




class TestContextManager:
    @pytest.mark.anyio
    async def test_async_context_manager(self):
        transport = MockTransport([_mock_response(200, {"status": "ok", "version": "0.0.2"})])
        http_client = httpx.AsyncClient(transport=transport)
        async with BigRAG(api_key="k", http_client=http_client) as client:
            result = await client.health()
            assert result["status"] == "ok"




class TestRetryLogic:
    @pytest.mark.anyio
    async def test_retry_on_429(self):
        transport = MockTransport([
            _mock_response(429, {"detail": "Rate limited"}),
            _mock_response(200, {"status": "ok", "version": "1.0"}),
        ])
        http_client = httpx.AsyncClient(transport=transport)
        client = BigRAG(api_key="k", http_client=http_client, max_retries=1)
        result = await client.health()
        assert result["status"] == "ok"
        assert len(transport.calls) == 2

    @pytest.mark.anyio
    async def test_retry_on_500(self):
        transport = MockTransport([
            _mock_response(500, {"detail": "Server error"}),
            _mock_response(200, {"status": "ok", "version": "1.0"}),
        ])
        http_client = httpx.AsyncClient(transport=transport)
        client = BigRAG(api_key="k", http_client=http_client, max_retries=1)
        result = await client.health()
        assert result["status"] == "ok"
        assert len(transport.calls) == 2

    @pytest.mark.anyio
    async def test_204_returns_ok(self):
        client, _ = _make_client([_mock_response(204)])
        result = await client.collections.delete("docs")
        assert result["status"] == "ok"

    @pytest.mark.anyio
    async def test_connection_error(self):
        class FailTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                raise httpx.ConnectError("Connection refused")
        http_client = httpx.AsyncClient(transport=FailTransport())
        client = BigRAG(api_key="k", http_client=http_client, max_retries=0)
        with pytest.raises(APIConnectionError):
            await client.health()

    @pytest.mark.anyio
    async def test_timeout_error(self):
        class TimeoutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                raise httpx.ReadTimeout("Read timed out")
        http_client = httpx.AsyncClient(transport=TimeoutTransport())
        client = BigRAG(api_key="k", http_client=http_client, max_retries=0)
        with pytest.raises(APITimeoutError):
            await client.health()




class TestFileUpload:
    @pytest.mark.anyio
    async def test_upload_bytes(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "doc1", "filename": "document"})]
        )
        await client.documents.upload("docs", b"PDF content")
        req = transport.calls[0]
        assert req.method == "POST"
        assert "/v1/collections/docs/documents" in str(req.url)
        assert b"PDF content" in req.content

    @pytest.mark.anyio
    async def test_upload_with_metadata(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "doc1"})]
        )
        await client.documents.upload("docs", b"data", metadata={"source": "test"})
        req = transport.calls[0]
        assert b"source" in req.content

    @pytest.mark.anyio
    async def test_upload_file_path(self, tmp_path):
        p = tmp_path / "report.pdf"
        p.write_bytes(b"PDF bytes")
        client, transport = _make_client(
            [_mock_response(200, {"id": "doc1", "filename": "report.pdf"})]
        )
        await client.documents.upload("docs", str(p))
        req = transport.calls[0]
        assert b"PDF bytes" in req.content
        assert b"report.pdf" in req.content




class TestSSEStreaming:
    @pytest.mark.anyio
    async def test_parse_sse_stream(self):
        from bigrag._sse import parse_sse_stream

        sse_data = (
            'data: {"step": "parsing", "message": "Parsing document", "progress": 0.5}\n'
            "\n"
            'data: {"step": "complete", "message": "Done", "progress": 1.0}\n'
            "\n"
        )

        class FakeResponse:
            """Mimics httpx.Response.aiter_lines()."""
            async def aiter_lines(self):
                for line in sse_data.split("\n"):
                    yield line

        events = []
        async for event in parse_sse_stream(FakeResponse()):
            events.append(event)

        assert len(events) == 2
        assert events[0]["step"] == "parsing"
        assert events[0]["progress"] == 0.5
        assert events[1]["step"] == "complete"
        assert events[1]["progress"] == 1.0

    @pytest.mark.anyio
    async def test_parse_sse_skips_malformed(self):
        from bigrag._sse import parse_sse_stream

        sse_data = (
            "data: not-json\n"
            "\n"
            'data: {"step": "ok", "message": "fine", "progress": 1.0}\n'
            "\n"
        )

        class FakeResponse:
            async def aiter_lines(self):
                for line in sse_data.split("\n"):
                    yield line

        events = []
        async for event in parse_sse_stream(FakeResponse()):
            events.append(event)

        assert len(events) == 1
        assert events[0]["step"] == "ok"

    @pytest.mark.anyio
    async def test_parse_sse_skips_non_data_lines(self):
        from bigrag._sse import parse_sse_stream

        sse_data = (
            "event: progress\n"
            ": comment\n"
            'data: {"step": "done", "message": "Done", "progress": 1.0}\n'
            "\n"
        )

        class FakeResponse:
            async def aiter_lines(self):
                for line in sse_data.split("\n"):
                    yield line

        events = []
        async for event in parse_sse_stream(FakeResponse()):
            events.append(event)

        assert len(events) == 1




class TestDocumentsBatchOps:
    @pytest.mark.anyio
    async def test_batch_get(self):
        client, transport = _make_client(
            [_mock_response(200, {"documents": [], "total": 0})]
        )
        await client.documents.batch_get("docs", ["a", "b"])
        body = json.loads(transport.calls[0].content)
        assert body["document_ids"] == ["a", "b"]
        assert "/batch/get" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_batch_delete(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "deleted": 2, "errors": []})]
        )
        result = await client.documents.batch_delete("docs", ["a", "b"])
        assert result["deleted"] == 2

    @pytest.mark.anyio
    async def test_get_chunks(self):
        client, transport = _make_client(
            [_mock_response(200, {"chunks": [{"id": "c1"}], "total": 1})]
        )
        result = await client.documents.get_chunks("docs", "doc1")
        assert result["total"] == 1
        assert "/chunks" in str(transport.calls[0].url)




class TestWebhooksExtended:
    @pytest.mark.anyio
    async def test_get_webhook(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "wh1", "url": "https://example.com"})]
        )
        result = await client.webhooks.get("wh1")
        assert result["id"] == "wh1"

    @pytest.mark.anyio
    async def test_update_webhook(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "wh1", "description": "updated"})]
        )
        await client.webhooks.update("wh1", {"description": "updated"})
        assert transport.calls[0].method == "PUT"
        assert json.loads(transport.calls[0].content)["description"] == "updated"

    @pytest.mark.anyio
    async def test_delete_webhook(self):
        client, transport = _make_client([_mock_response(204)])
        await client.webhooks.delete("wh1")
        assert transport.calls[0].method == "DELETE"

    @pytest.mark.anyio
    async def test_list_deliveries(self):
        client, transport = _make_client(
            [_mock_response(200, {"deliveries": [], "total": 0})]
        )
        await client.webhooks.list_deliveries("wh1", limit=10, offset=20)
        url = str(transport.calls[0].url)
        assert "limit=10" in url
        assert "offset=20" in url




class TestCollectionClientExtended:
    @pytest.mark.anyio
    async def test_scoped_list_documents(self):
        client, transport = _make_client(
            [_mock_response(200, {"documents": [], "total": 0})]
        )
        col = client.collection("mydata")
        await col.list_documents(limit=5)
        url = str(transport.calls[0].url)
        assert "/v1/collections/mydata/documents" in url
        assert "limit=5" in url

    @pytest.mark.anyio
    async def test_scoped_get_document(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "doc1"})]
        )
        col = client.collection("mydata")
        await col.get_document("doc1")
        assert "/v1/collections/mydata/documents/doc1" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_delete_document(self):
        client, transport = _make_client([_mock_response(204)])
        col = client.collection("mydata")
        await col.delete_document("doc1")
        assert transport.calls[0].method == "DELETE"

    @pytest.mark.anyio
    async def test_scoped_reprocess(self):
        client, transport = _make_client([_mock_response(200, {"status": "ok"})])
        col = client.collection("mydata")
        await col.reprocess_document("doc1")
        assert "/reprocess" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_batch_get_status(self):
        client, transport = _make_client(
            [_mock_response(200, {"documents": [], "total": 0})]
        )
        col = client.collection("mydata")
        await col.batch_get_status(["id1"])
        assert "/batch/status" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_batch_delete(self):
        client, transport = _make_client(
            [_mock_response(200, {"status": "ok", "deleted": 1, "errors": []})]
        )
        col = client.collection("mydata")
        await col.batch_delete(["id1"])
        assert "/batch/delete" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_analytics(self):
        client, transport = _make_client(
            [_mock_response(200, {"collection": "mydata"})]
        )
        col = client.collection("mydata")
        await col.analytics()
        assert "/v1/collections/mydata/analytics" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_scoped_get_chunks(self):
        client, transport = _make_client(
            [_mock_response(200, {"chunks": [], "total": 0})]
        )
        col = client.collection("mydata")
        await col.get_document_chunks("doc1")
        assert "/chunks" in str(transport.calls[0].url)




class TestEmbeddingModels:
    @pytest.mark.anyio
    async def test_list_embedding_models(self):
        client, transport = _make_client(
            [_mock_response(200, {"models": [{"provider": "openai", "model": "text-embedding-3-small"}]})]
        )
        result = await client.list_embedding_models()
        assert len(result["models"]) == 1
        assert "/v1/embeddings/models" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_get_analytics(self):
        client, transport = _make_client(
            [_mock_response(200, {"collection": "docs", "period_24h": {"query_count": 10}})]
        )
        result = await client.get_analytics("docs")
        assert result["collection"] == "docs"
        assert "/v1/collections/docs/analytics" in str(transport.calls[0].url)




class TestEnvApiKey:
    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("BIGRAG_API_KEY", "from-env")
        client = BigRAG()
        assert client.api_key == "from-env"

    def test_option_overrides_env(self, monkeypatch):
        monkeypatch.setenv("BIGRAG_API_KEY", "from-env")
        client = BigRAG(api_key="from-option")
        assert client.api_key == "from-option"

    def test_defaults_to_empty(self, monkeypatch):
        monkeypatch.delenv("BIGRAG_API_KEY", raising=False)
        client = BigRAG()
        assert client.api_key == ""




class TestURLEncoding:
    @pytest.mark.anyio
    async def test_encodes_spaces_in_collection_name(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "1", "name": "my collection"})]
        )
        await client.collections.get("my collection")
        assert "my%20collection" in str(transport.calls[0].url)

    @pytest.mark.anyio
    async def test_encodes_slashes_in_name(self):
        client, transport = _make_client(
            [_mock_response(200, {"id": "1", "name": "a/b"})]
        )
        await client.collections.get("a/b")
        url = str(transport.calls[0].url)
        assert "a%2Fb" in url
