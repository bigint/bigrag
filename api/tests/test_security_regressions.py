from __future__ import annotations

import asyncio
import io
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from starlette.responses import PlainTextResponse

from bigrag.middleware import idempotency
from bigrag.models import webhook as webhook_models
from bigrag.routers import documents
from bigrag.services import embedding, file_validation, mcp_http, queue


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

    monkeypatch.setattr(webhook_models.socket, "getaddrinfo", fail_getaddrinfo)

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

    monkeypatch.setattr(webhook_models.socket, "getaddrinfo", public_addrinfo)
    _run(webhook_models.resolve_and_validate_url("https://example.com/webhook"))

    monkeypatch.setattr(webhook_models.socket, "getaddrinfo", private_addrinfo)
    with pytest.raises(ValueError, match="private or internal"):
        _run(webhook_models.resolve_and_validate_url("https://example.com/webhook"))


def test_embedding_semaphores_are_partitioned_by_provider_or_endpoint() -> None:
    embedding._embed_semaphores.clear()

    openai_default = embedding._get_semaphore("openai:default")
    openai_default_again = embedding._get_semaphore("openai:default")
    cohere = embedding._get_semaphore("cohere")

    assert openai_default is openai_default_again
    assert openai_default is not cohere
