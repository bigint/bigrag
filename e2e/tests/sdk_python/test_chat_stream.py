"""SDK contract tests for ``bigrag.ChatResource``.

Touches every public method::

    create, stream

plus the :meth:`bigrag.BigRAG.chat_create` and :meth:`bigrag.BigRAG.chat_stream`
client-level wrappers.

The fake-openai stub returns a deterministic canned response of the form
``"Based on the provided context, <last user message> (answered by
fake-openai)."``, so we can assert non-empty content without flakes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from bigrag import BigRAG, NotFoundError


async def test_chat_create_non_streaming_returns_typed_envelope(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.chat.create(
        {"collection": coll["name"], "message": "What does this document say?"}
    )

    assert "message" in response
    assert "assistant_message" in response
    assert "sources" in response
    assert isinstance(response["sources"], list)

    user_msg = response["message"]
    for key in ("id", "role", "content", "status", "created_at"):
        assert key in user_msg
    assert user_msg["role"] == "user"

    assistant = response["assistant_message"]
    assert assistant["role"] == "assistant"
    assert isinstance(assistant["content"], str)
    assert len(assistant["content"]) > 0
    assert "fake-openai" in assistant["content"]


async def test_chat_stream_yields_typed_events_and_content(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    deltas: list[str] = []
    events: list[str] = []
    sources_payload: dict[str, Any] | None = None
    assistant_payload: dict[str, Any] | None = None

    async for event in client.chat.stream(
        {"collection": coll["name"], "message": "Summarise the document"}
    ):
        assert isinstance(event, dict)
        assert "event" in event and "data" in event
        events.append(event["event"])
        if event["event"] == "delta":
            piece = event["data"].get("delta", "")
            assert isinstance(piece, str)
            deltas.append(piece)
        elif event["event"] == "sources":
            sources_payload = event["data"]
        elif event["event"] == "assistant_message":
            assistant_payload = event["data"]

    assert "delta" in events
    assert "done" in events
    assert sources_payload is not None
    assert "sources" in sources_payload
    assert isinstance(sources_payload["sources"], list)
    full = "".join(deltas)
    assert full.strip(), "expected non-empty streamed content"
    assert "fake-openai" in full
    assert assistant_payload is not None
    assert assistant_payload["content"] == full


async def test_chat_stream_citations_link_to_sources(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")

    sources_payload: dict[str, Any] | None = None
    async for event in client.chat.stream(
        {"collection": coll["name"], "message": "Tell me about the document"}
    ):
        if event["event"] == "sources":
            sources_payload = event["data"]
            break

    assert sources_payload is not None
    sources = sources_payload["sources"]
    assert sources, "expected at least one retrieved source"
    first = sources[0]
    for key in ("id", "text", "score", "document_id", "metadata"):
        assert key in first
    assert first["document_id"] == doc["id"]


async def test_chat_client_aliases_create_and_stream(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """``BigRAG.chat_create`` / ``BigRAG.chat_stream`` mirror the resource."""
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    non_stream = await client.chat_create({"collection": coll["name"], "message": "hello"})
    assert non_stream["assistant_message"]["role"] == "assistant"

    saw_event = False
    async for event in client.chat_stream({"collection": coll["name"], "message": "hello stream"}):
        saw_event = True
        if event["event"] == "done":
            break
    assert saw_event


async def test_chat_unknown_collection_raises(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    with pytest.raises(NotFoundError):
        await client.chat.create({"collection": "missing-xyz", "message": "hi"})


async def test_chat_temperature_and_top_k_pass_through(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Optional knobs should round-trip without rejection from the server."""
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.chat.create(
        {
            "collection": coll["name"],
            "message": "Tell me",
            "temperature": 0.0,
            "top_k": 2,
            "search_mode": "semantic",
        }
    )
    assert response["assistant_message"]["content"]
