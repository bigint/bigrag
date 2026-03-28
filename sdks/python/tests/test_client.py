"""Unit tests for the bigRAG Python SDK."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

import bigrag
from bigrag import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncBigRAG,
    AuthenticationError,
    BadRequestError,
    BigRAG,
    BigRAGError,
    Document,
    InternalServerError,
    NamespaceListResponse,
    NotFoundError,
    QueryResponse,
    RateLimitError,
    WriteResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        content=json.dumps(json_data).encode() if json_data else text.encode(),
        headers={"content-type": "application/json"} if json_data else {},
        request=httpx.Request("GET", "http://test"),
    )
    return resp


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------


class TestClientInit:
    def test_defaults(self):
        client = BigRAG(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "http://localhost:8080"
        assert client.timeout == 60.0
        assert client.max_retries == 2

    def test_custom_params(self):
        client = BigRAG(
            api_key="key",
            base_url="http://custom:9090/",
            timeout=30.0,
            max_retries=5,
        )
        assert client.base_url == "http://custom:9090"
        assert client.timeout == 30.0
        assert client.max_retries == 5

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("BIGRAG_API_KEY", "env-key")
        client = BigRAG()
        assert client.api_key == "env-key"

    def test_headers_include_auth(self):
        client = BigRAG(api_key="secret")
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer secret"

    def test_headers_no_auth_when_empty(self):
        client = BigRAG(api_key="")
        headers = client._build_headers()
        assert "Authorization" not in headers

    def test_context_manager(self):
        with BigRAG(api_key="k") as client:
            assert isinstance(client, BigRAG)

    def test_version(self):
        assert bigrag.__version__ == "0.1.0"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health(self):
        client = BigRAG(api_key="k")
        mock_resp = _make_response(200, {"status": "ok", "version": "0.1.0"})
        with patch.object(client._client, "request", return_value=mock_resp):
            result = client.health()
        assert result["status"] == "ok"
        assert result["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# Namespaces listing
# ---------------------------------------------------------------------------


class TestNamespaces:
    def test_list_namespaces(self):
        client = BigRAG(api_key="k")
        mock_resp = _make_response(
            200,
            {
                "namespaces": [{"id": "ns1"}, {"id": "ns2"}],
                "next_cursor": None,
            },
        )
        with patch.object(client._client, "request", return_value=mock_resp):
            result = client.namespaces()
        assert isinstance(result, NamespaceListResponse)
        assert len(result.namespaces) == 2
        assert result.namespaces[0].id == "ns1"
        assert result.next_cursor is None


# ---------------------------------------------------------------------------
# Namespace operations
# ---------------------------------------------------------------------------


class TestNamespaceOps:
    def setup_method(self):
        self.client = BigRAG(api_key="k")
        self.ns = self.client.namespace("test-ns")

    def test_namespace_repr(self):
        assert repr(self.ns) == "Namespace('test-ns')"

    def test_upsert(self):
        mock_resp = _make_response(
            200, {"status": "ok", "rows_affected": 2}
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            result = self.ns.upsert(
                [
                    {"id": 1, "vector": [0.1, 0.2], "title": "hello"},
                    Document(id=2, vector=[0.3, 0.4], attributes={"title": "world"}),
                ],
                distance_metric="cosine_distance",
            )
        assert isinstance(result, WriteResponse)
        assert result.rows_affected == 2

        call_kwargs = mock_req.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(body["upsert_rows"]) == 2
        assert body["distance_metric"] == "cosine_distance"

    def test_query(self):
        mock_resp = _make_response(
            200,
            {
                "rows": [
                    {"id": 1, "dist": 0.1, "title": "hello"},
                    {"id": 2, "dist": 0.5, "title": "world"},
                ]
            },
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ):
            result = self.ns.query(
                rank_by=["vector", "ANN", [0.1, 0.2]],
                top_k=5,
                include_attributes=True,
            )
        assert isinstance(result, QueryResponse)
        assert len(result.rows) == 2
        assert result.rows[0].id == 1
        assert result.rows[0].dist == 0.1
        assert result.rows[0].attributes["title"] == "hello"

    def test_delete_ids(self):
        mock_resp = _make_response(
            200, {"status": "ok", "rows_affected": 1}
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            result = self.ns.delete([1, 2])
        assert result.rows_affected == 1
        body = mock_req.call_args.kwargs.get("json") or mock_req.call_args[1].get("json")
        assert body["delete_ids"] == [1, 2]

    def test_delete_all(self):
        mock_resp = _make_response(200, {"status": "ok"})
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            self.ns.delete_all()
        assert mock_req.call_args[0][0] == "DELETE"

    def test_delete_by_filter(self):
        mock_resp = _make_response(
            200, {"status": "ok", "rows_affected": 42}
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            result = self.ns.delete_by_filter(["category", "Eq", "spam"])
        assert result.rows_affected == 42

    def test_patch(self):
        mock_resp = _make_response(
            200, {"status": "ok", "rows_affected": 1}
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            result = self.ns.patch([{"id": 1, "title": "updated"}])
        assert result.rows_affected == 1
        body = mock_req.call_args.kwargs.get("json") or mock_req.call_args[1].get("json")
        assert body["patch_rows"] == [{"id": 1, "title": "updated"}]

    def test_metadata(self):
        mock_resp = _make_response(
            200, {"schema": {"title": "string"}, "approx_row_count": 1000}
        )
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ):
            meta = self.ns.metadata()
        assert meta.approx_row_count == 1000
        assert meta.schema == {"title": "string"}

    def test_schema(self):
        mock_resp = _make_response(200, {"title": "string", "score": "float"})
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ):
            schema = self.ns.schema()
        assert schema["title"] == "string"

    def test_update_schema(self):
        mock_resp = _make_response(200, {"status": "ok"})
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ) as mock_req:
            self.ns.update_schema({"title": "string"})
        assert mock_req.call_args[0][0] == "PUT"

    def test_recall(self):
        mock_resp = _make_response(200, {"avg_recall": 0.98})
        with patch.object(
            self.client._client, "request", return_value=mock_resp
        ):
            result = self.ns.recall(num=50, top_k=20)
        assert result["avg_recall"] == 0.98


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_400_raises_bad_request(self):
        client = BigRAG(api_key="k")
        mock_resp = _make_response(400, {"error": "invalid body"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(BadRequestError) as exc_info:
                client.health()
            assert exc_info.value.status_code == 400
            assert "invalid body" in exc_info.value.message

    def test_401_raises_auth_error(self):
        client = BigRAG(api_key="bad")
        mock_resp = _make_response(401, {"error": "unauthorized"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(AuthenticationError):
                client.health()

    def test_404_raises_not_found(self):
        client = BigRAG(api_key="k")
        mock_resp = _make_response(404, {"error": "not found"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(NotFoundError):
                client.namespace("missing").metadata()

    def test_429_raises_rate_limit(self):
        client = BigRAG(api_key="k", max_retries=0)
        mock_resp = _make_response(429, {"error": "rate limited"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(RateLimitError):
                client.health()

    def test_500_raises_internal_server_error(self):
        client = BigRAG(api_key="k", max_retries=0)
        mock_resp = _make_response(500, {"error": "server error"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(InternalServerError):
                client.health()

    def test_unknown_status_raises_api_error(self):
        client = BigRAG(api_key="k", max_retries=0)
        mock_resp = _make_response(418, {"error": "teapot"})
        with patch.object(client._client, "request", return_value=mock_resp):
            with pytest.raises(APIError) as exc_info:
                client.health()
            assert exc_info.value.status_code == 418

    def test_timeout_raises_timeout_error(self):
        client = BigRAG(api_key="k", max_retries=0)
        with patch.object(
            client._client,
            "request",
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            with pytest.raises(APITimeoutError):
                client.health()

    def test_connection_error_raises(self):
        client = BigRAG(api_key="k", max_retries=0)
        with patch.object(
            client._client,
            "request",
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(APIConnectionError):
                client.health()

    def test_error_hierarchy(self):
        assert issubclass(APIError, BigRAGError)
        assert issubclass(BadRequestError, APIError)
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(NotFoundError, APIError)
        assert issubclass(RateLimitError, APIError)
        assert issubclass(InternalServerError, APIError)
        assert issubclass(APIConnectionError, BigRAGError)
        assert issubclass(APITimeoutError, BigRAGError)


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class TestRetries:
    def test_retries_on_500(self):
        client = BigRAG(api_key="k", max_retries=2)
        fail = _make_response(500, {"error": "fail"})
        ok = _make_response(200, {"status": "ok"})
        with patch.object(
            client._client, "request", side_effect=[fail, fail, ok]
        ):
            result = client.health()
        assert result["status"] == "ok"

    def test_retries_on_429(self):
        client = BigRAG(api_key="k", max_retries=1)
        rate_limit = _make_response(429, {"error": "slow down"})
        ok = _make_response(200, {"status": "ok"})
        with patch.object(
            client._client, "request", side_effect=[rate_limit, ok]
        ):
            result = client.health()
        assert result["status"] == "ok"

    def test_retries_on_timeout(self):
        client = BigRAG(api_key="k", max_retries=1)
        ok = _make_response(200, {"status": "ok"})
        with patch.object(
            client._client,
            "request",
            side_effect=[httpx.ReadTimeout("timeout"), ok],
        ):
            result = client.health()
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TestTypes:
    def test_document_to_dict(self):
        doc = Document(id=1, vector=[0.1, 0.2], attributes={"title": "hi"})
        d = doc.to_dict()
        assert d == {"id": 1, "vector": [0.1, 0.2], "title": "hi"}

    def test_document_to_dict_no_vector(self):
        doc = Document(id=1, attributes={"title": "hi"})
        d = doc.to_dict()
        assert d == {"id": 1, "title": "hi"}
        assert "vector" not in d

    def test_query_row_from_dict(self):
        from bigrag import QueryRow

        row = QueryRow.from_dict(
            {"id": 1, "dist": 0.5, "vector": [0.1], "title": "hi"}
        )
        assert row.id == 1
        assert row.dist == 0.5
        assert row.vector == [0.1]
        assert row.attributes == {"title": "hi"}

    def test_write_response_from_dict(self):
        wr = WriteResponse.from_dict({"status": "ok", "rows_affected": 5})
        assert wr.status == "ok"
        assert wr.rows_affected == 5


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class TestAsyncClient:
    def test_async_client_init(self):
        client = AsyncBigRAG(api_key="key", base_url="http://host:1234")
        assert client.api_key == "key"
        assert client.base_url == "http://host:1234"

    def test_async_namespace_returns_async_namespace(self):
        from bigrag.namespace import AsyncNamespace

        client = AsyncBigRAG(api_key="k")
        ns = client.namespace("test")
        assert isinstance(ns, AsyncNamespace)
        assert repr(ns) == "AsyncNamespace('test')"
