from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bigrag.models.playground import PlaygroundChatRequest
from bigrag.routers.playground import (
    _get_playground_openai_key,
    _safe_openai_error,
    _stream_openai_chat,
)


def _run(coro):
    return asyncio.run(coro)


async def _collect(async_iter):
    return [item async for item in async_iter]


def test_safe_openai_error_redacts_api_keys() -> None:
    err = RuntimeError("bad key sk-secretvalue123456")

    assert _safe_openai_error(err) == "bad key sk-[REDACTED]"


def test_get_playground_openai_key_reads_saved_preference() -> None:
    class FakeSession:
        async def scalar(self, _stmt):
            return {"playground": {"openai_key": " sk-test "}}

    key = _run(_get_playground_openai_key("00000000-0000-0000-0000-000000000000", FakeSession()))

    assert key == "sk-test"


def test_get_playground_openai_key_requires_saved_key() -> None:
    class FakeSession:
        async def scalar(self, _stmt):
            return {"playground": {}}

    with pytest.raises(HTTPException) as exc:
        _run(_get_playground_openai_key("00000000-0000-0000-0000-000000000000", FakeSession()))

    assert exc.value.status_code == 400
    assert exc.value.detail == "Add an OpenAI API key first"


def test_stream_openai_chat_emits_backend_sse(monkeypatch) -> None:
    class FakeCompletions:
        def __init__(self, client):
            self.client = client

        async def create(self, **kwargs):
            self.client.kwargs = kwargs

            async def chunks():
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]
                )

            return chunks()

    class FakeClient:
        last = None

        def __init__(self, *, api_key):
            self.api_key = api_key
            self.closed = False
            self.kwargs = {}
            self.chat = SimpleNamespace(completions=FakeCompletions(self))
            FakeClient.last = self

        async def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeClient))

    body = PlaygroundChatRequest(
        model="gpt-test",
        temperature=0.3,
        messages=[{"role": "user", "content": "question"}],
    )
    frames = _run(_collect(_stream_openai_chat(body, api_key="sk-test")))

    assert frames == ['data: {"delta":"hello"}\n\n', "data: [DONE]\n\n"]
    assert FakeClient.last is not None
    assert FakeClient.last.api_key == "sk-test"
    assert FakeClient.last.closed is True
    assert FakeClient.last.kwargs["stream"] is True
    assert FakeClient.last.kwargs["messages"] == [{"role": "user", "content": "question"}]
