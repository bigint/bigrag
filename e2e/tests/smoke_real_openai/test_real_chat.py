"""Real-OpenAI smoke tests for chat (non-streaming + streaming).

Two real chat completions per run, both against ``gpt-4o-mini`` with a
tiny user message. Prompts are intentionally trivial ("Reply with the
word OK.") so output tokens stay near zero.

Total cost per file: well under $0.001 at current ``gpt-4o-mini`` rates.

The whole module is skipped unless ``BIGRAG_E2E_REAL_OPENAI=1`` (see
``conftest.py`` in this directory).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope

SHORT_PROMPT = "Reply with the word OK."


async def _seeded_collection(
    real_openai_settings: dict[str, object],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    coll = await collection(dimension=int(real_openai_settings["embedding_dimension"]))
    await document(coll["name"], fixture="sample.txt")
    return coll


async def test_real_openai_chat_non_streaming(
    real_openai_settings: dict[str, object],
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await _seeded_collection(real_openai_settings, collection, document)

    resp = await admin_client.post(
        "/v1/chat",
        json={
            "message": SHORT_PROMPT,
            "collection": coll["name"],
            "stream": False,
            "top_k": 1,
        },
    )
    body = assert_envelope(resp, 200)

    assistant = body["assistant_message"]
    assert assistant["status"] == "complete", assistant
    assert isinstance(assistant["content"], str) and assistant["content"].strip(), assistant
    assert isinstance(body["sources"], list)


async def test_real_openai_chat_streaming(
    real_openai_settings: dict[str, object],
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await _seeded_collection(real_openai_settings, collection, document)

    delta_chunks: list[str] = []
    assistant_payload: dict[str, Any] | None = None

    async with admin_client.stream(
        "POST",
        "/v1/chat",
        json={
            "message": SHORT_PROMPT,
            "collection": coll["name"],
            "stream": True,
            "top_k": 1,
        },
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        event_name: str | None = None
        data_buffer: list[str] = []

        async for raw_line in resp.aiter_lines():
            if raw_line == "":
                if event_name and data_buffer:
                    payload = "\n".join(data_buffer)
                    if payload != "[DONE]":
                        try:
                            parsed = json.loads(payload)
                        except json.JSONDecodeError:
                            parsed = None
                        if event_name == "delta" and isinstance(parsed, dict):
                            delta = parsed.get("delta")
                            if isinstance(delta, str):
                                delta_chunks.append(delta)
                        elif event_name == "assistant_message" and isinstance(parsed, dict):
                            assistant_payload = parsed
                event_name = None
                data_buffer = []
                continue
            if raw_line.startswith("event:"):
                event_name = raw_line.split(":", 1)[1].strip()
            elif raw_line.startswith("data:"):
                data_buffer.append(raw_line.split(":", 1)[1].lstrip())

    assert delta_chunks, "no delta chunks received from streaming chat"
    final_content = "".join(delta_chunks).strip()
    assert final_content, "streamed content was empty"

    if assistant_payload is not None:
        assert assistant_payload.get("status") == "complete", assistant_payload
        assert (assistant_payload.get("content") or "").strip(), assistant_payload
