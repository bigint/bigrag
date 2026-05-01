from __future__ import annotations

import asyncio
import io
import uuid
from types import SimpleNamespace

import orjson
import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from starlette.responses import PlainTextResponse

from bigrag.config import settings
from bigrag.middleware import idempotency
from bigrag.models import webhook as webhook_models
from bigrag.routers import documents
from bigrag.routers._documents import UploadBudget
from bigrag.services import (
    collection_scope,
    embedding,
    file_validation,
    mcp_http,
    queue,
    rate_limit,
    url_security,
)
from bigrag.services.ingestion_job import create_ingestion_job


def _run(coro):
    return asyncio.run(coro)


def test_mcp_http_ignores_query_token_and_uses_bearer_header() -> None:
    async def read_token(query_params: dict[str, str], headers: dict[str, str]) -> str | None:
        seen: list[str | None] = []
        middleware = mcp_http._TokenExtractMiddleware(lambda _scope, _receive, _send: None)

        async def call_next(_request):
            seen.append(mcp_http._current_token.get())
            return PlainTextResponse("ok")

        request = SimpleNamespace(query_params=query_params, headers=headers)
        await middleware.dispatch(request, call_next)
        return seen[0]

    assert _run(read_token({"token": "bigrag_sk_query"}, {})) is None
    assert _run(read_token({}, {"authorization": "Bearer bigrag_sk_header"})) == "bigrag_sk_header"


def test_mcp_http_tool_path_inputs_are_constrained() -> None:
    collection_adapter = TypeAdapter(mcp_http.CollectionName)
    document_adapter = TypeAdapter(mcp_http.DocumentId)

    assert collection_adapter.validate_python("Docs_2026") == "Docs_2026"
    assert document_adapter.validate_python("123e4567-e89b-12d3-a456-426614174000")

    with pytest.raises(ValidationError):
        collection_adapter.validate_python("../admin")
    with pytest.raises(ValidationError):
        collection_adapter.validate_python("docs/other")
    with pytest.raises(ValidationError):
        document_adapter.validate_python("../admin")


def test_idempotency_skips_large_response_bodies(monkeypatch) -> None:
    set_calls: list[dict] = []

    async def fake_get(_key):
        return None

    async def fake_set(key, value, ttl):
        set_calls.append({"key": key, "value": value, "ttl": ttl})

    async def app(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {
                "type": "http.response.body",
                "body": b"x" * (idempotency._MAX_CACHED_BODY_BYTES + 1),
            }
        )

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    monkeypatch.setattr(idempotency.redis_cache, "get", fake_get)
    monkeypatch.setattr(idempotency.redis_cache, "set", fake_set)

    middleware = idempotency.IdempotencyMiddleware(app)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/test",
        "headers": [(b"idempotency-key", b"abc")],
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
    }
    _run(middleware(scope, receive, send))

    assert set_calls == []
    assert sent[-1]["body"] == b"x" * (idempotency._MAX_CACHED_BODY_BYTES + 1)


def test_zip_bomb_validation_streams_member_bytes(monkeypatch) -> None:
    class FakeInfo:
        file_size = 0

        def is_dir(self) -> bool:
            return False

    class FakeZipFile:
        def __init__(self, _content) -> None:
            self.closed = False

        def infolist(self):
            return [FakeInfo()]

        def open(self, _info):
            return io.BytesIO(b"x" * 20)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(file_validation, "MAX_DECOMPRESSED_BYTES", 10)
    monkeypatch.setattr(file_validation.zipfile, "ZipFile", FakeZipFile)

    with pytest.raises(file_validation.InvalidFileContentError, match="Archive too large"):
        file_validation.validate_zip_bomb(b"PK", ".docx")


def test_embedding_cache_uses_truncated_text_and_deduplicates_misses(monkeypatch) -> None:
    get_calls: list[list[str]] = []
    put_calls: list[tuple[list[str], list[list[float]]]] = []

    class FakeModel:
        def __init__(self) -> None:
            self.inputs: list[str] = []

        async def embed(self, texts: list[str], *, input_type: str = "document"):
            self.inputs.extend(texts)
            return [[1.0] for _ in texts]

    async def fake_get_many(texts, _provider, _model, _dimension):
        get_calls.append(list(texts))
        return {}

    async def fake_put_many(texts, vectors, _provider, _model, _dimension):
        put_calls.append((list(texts), vectors))

    monkeypatch.setattr(queue, "truncate_to_tokens", lambda texts, _model: (["same", "same"], []))
    monkeypatch.setattr(queue.embedding_cache, "get_many", fake_get_many)
    monkeypatch.setattr(queue.embedding_cache, "put_many", fake_put_many)

    model = FakeModel()
    result = _run(queue._embed_with_cache(["same before A", "same before B"], model, "p", "m", 1))

    assert get_calls == [["same", "same"]]
    assert model.inputs == ["same before A"]
    assert put_calls == [(["same"], [[1.0]])]
    assert result == [[1.0], [1.0]]


def test_batch_progress_document_helpers_reject_invalid_or_cross_collection_ids() -> None:
    doc_id = uuid.uuid4()
    other_id = uuid.uuid4()

    doc_ids, doc_uuids = documents._parse_progress_document_ids([str(doc_id), str(doc_id)])

    assert doc_ids == [str(doc_id)]
    assert doc_uuids == [doc_id]

    with pytest.raises(HTTPException) as invalid:
        documents._parse_progress_document_ids(["not-a-uuid"])
    assert invalid.value.status_code == 400

    class FakeSession:
        async def scalars(self, _stmt):
            return [doc_id]

    with pytest.raises(HTTPException) as missing:
        _run(
            documents._ensure_documents_in_collection(
                FakeSession(),
                uuid.uuid4(),
                [doc_id, other_id],
            )
        )
    assert missing.value.status_code == 404


def test_webhook_request_validation_does_not_resolve_dns(monkeypatch) -> None:
    def fail_getaddrinfo(*_args, **_kwargs):
        raise AssertionError("DNS should not run inside pydantic validation")

    monkeypatch.setattr(url_security.socket, "getaddrinfo", fail_getaddrinfo)

    request = webhook_models.CreateWebhookRequest(
        url="https://example.com/webhook",
        events=["document.ready"],
    )

    assert request.url == "https://example.com/webhook"


def test_webhook_async_dns_validation_blocks_private_targets(monkeypatch) -> None:
    def public_addrinfo(_hostname, port):
        return [(None, None, None, None, ("8.8.8.8", port))]

    def private_addrinfo(_hostname, port):
        return [(None, None, None, None, ("10.0.0.1", port))]

    monkeypatch.setattr(url_security.socket, "getaddrinfo", public_addrinfo)
    _run(webhook_models.resolve_and_validate_url("https://example.com/webhook"))

    monkeypatch.setattr(url_security.socket, "getaddrinfo", private_addrinfo)
    with pytest.raises(ValueError, match="private"):
        _run(webhook_models.resolve_and_validate_url("https://example.com/webhook"))


def test_webhook_validation_blocks_loopback_by_default(monkeypatch) -> None:
    def loopback_addrinfo(_hostname, port):
        return [(None, None, None, None, ("127.0.0.1", port))]

    monkeypatch.setattr(url_security.socket, "getaddrinfo", loopback_addrinfo)
    monkeypatch.setattr(settings, "allow_local_webhooks", False)

    with pytest.raises(ValueError, match="loopback"):
        _run(webhook_models.resolve_and_validate_url("https://localhost/webhook"))


def test_embedding_base_url_blocks_metadata_and_private_targets(monkeypatch) -> None:
    def metadata_addrinfo(_hostname, port):
        return [(None, None, None, None, ("169.254.169.254", port))]

    monkeypatch.setattr(url_security.socket, "getaddrinfo", metadata_addrinfo)
    monkeypatch.setattr(settings, "allowed_embedding_base_urls", [])
    monkeypatch.setattr(settings, "allow_private_embedding_base_urls", False)

    with pytest.raises(url_security.UnsafeOutboundUrlError, match="link-local"):
        url_security.validate_embedding_base_url_sync("https://metadata.example/v1")


def test_embedding_base_url_can_be_explicitly_allowlisted(monkeypatch) -> None:
    def fail_getaddrinfo(*_args, **_kwargs):
        raise AssertionError("allowlisted URLs should not require DNS resolution")

    monkeypatch.setattr(url_security.socket, "getaddrinfo", fail_getaddrinfo)
    monkeypatch.setattr(settings, "allowed_embedding_base_urls", ["http://ollama:11434/v1"])

    assert (
        url_security.validate_embedding_base_url_sync("http://ollama:11434/v1")
        == "http://ollama:11434/v1"
    )


def test_pinned_collection_keys_cannot_use_global_stats_or_usage() -> None:
    for path in ("/v1/usage", "/v1/stats", "/v1/embeddings/models"):
        request = SimpleNamespace(method="GET", url=SimpleNamespace(path=path))
        with pytest.raises(HTTPException) as exc:
            _run(collection_scope.enforce_collection_scope(request, "docs"))
        assert exc.value.status_code == 403


def test_ingestion_jobs_do_not_serialize_embedding_api_keys() -> None:
    job = create_ingestion_job(
        document_id=str(uuid.uuid4()),
        file_path="docs/doc.txt",
        collection_name="docs",
        collection={
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "dimension": 1536,
            "embedding_api_key": "sk-secret",
            "embedding_base_url": "https://api.openai.com/v1",
            "chunk_size": 512,
            "chunk_overlap": 50,
        },
        fallback_api_key="sk-fallback",
    )

    payload = orjson.loads(job.serialize())

    assert "embedding_api_key" not in payload
    assert not hasattr(job, "embedding_api_key")


def test_upload_budget_enforces_cumulative_batch_size() -> None:
    budget = UploadBudget(max_size=4)
    budget.consume(2)
    with pytest.raises(HTTPException) as exc:
        budget.consume(3)
    assert exc.value.status_code == 413


def test_auth_rate_limit_raises_after_limit(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.count = 0

        async def incr(self, _key):
            self.count += 1
            return self.count

        async def expire(self, _key, _ttl):
            return None

        async def ttl(self, _key):
            return 30

    fake = FakeRedis()
    monkeypatch.setattr(rate_limit, "get_redis", lambda: fake)

    _run(
        rate_limit.consume_rate_limit(
            bucket="auth:test",
            identifier="user@example.com",
            limit=1,
            window_seconds=60,
            message="Too many attempts",
        )
    )
    with pytest.raises(HTTPException) as exc:
        _run(
            rate_limit.consume_rate_limit(
                bucket="auth:test",
                identifier="user@example.com",
                limit=1,
                window_seconds=60,
                message="Too many attempts",
            )
        )
    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "30"}


def test_embedding_semaphores_are_partitioned_by_provider_or_endpoint() -> None:
    embedding._embed_semaphores.clear()

    openai_default = embedding._get_semaphore("openai:default")
    openai_default_again = embedding._get_semaphore("openai:default")
    cohere = embedding._get_semaphore("cohere")

    assert openai_default is openai_default_again
    assert openai_default is not cohere
