"""End-to-end tests for bigrag.routers.chat.

Endpoints covered:
- POST /v1/chat               (non-streaming)
- POST /v1/chat (stream=true) (text/event-stream)
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from tests._helpers import assert_envelope, wait_until_searchable


CollectionFactory = Callable[..., Awaitable[dict[str, Any]]]
DocumentFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


# ---------------------------------------------------------------------------
# Non-streaming chat
# ---------------------------------------------------------------------------


async def test_chat_non_streaming_returns_assistant_with_sources(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    assert doc["status"] == "ready"
    await wait_until_searchable(admin_client, coll["name"], "Acme Corp", top_k=3)

    resp = await admin_client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Who founded Acme Corp and where?",
            "stream": False,
            "top_k": 5,
        },
    )
    body = assert_envelope(resp, 200)
    assert "message" in body
    assert "assistant_message" in body
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]
    assert isinstance(body["sources"], list)
    source_ids = {s.get("document_id") for s in body["sources"]}
    assert str(doc["id"]) in source_ids, (source_ids, doc["id"])
    assert "timings" in body and body["timings"]


async def test_chat_non_streaming_model_override_propagates(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    resp = await admin_client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Who founded Acme Corp?",
            "stream": False,
            "model": "gpt-4o-mini",
        },
    )
    body = assert_envelope(resp, 200)
    assert body["assistant_message"]["model"] == "gpt-4o-mini"


async def test_chat_non_streaming_top_k_passes_through(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    resp = await admin_client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Acme",
            "stream": False,
            "top_k": 2,
        },
    )
    body = assert_envelope(resp, 200)
    assert len(body["sources"]) <= 2


async def test_chat_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.post(
        "/v1/chat",
        json={"collection": "x", "message": "hi", "stream": False},
    )
    assert resp.status_code == 401, resp.text


async def test_chat_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/chat",
        json={
            "collection": "chat-missing-coll-xyz",
            "message": "hi",
            "stream": False,
        },
    )
    assert resp.status_code == 404, resp.text


async def test_chat_api_key_without_chat_write_scope_403(
    api_key: ApiKeyFactory,
    api_key_client: ApiKeyClientFactory,
    collection: CollectionFactory,
    document: DocumentFactory,
    admin_client: httpx.AsyncClient,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    key = await api_key(scopes=["query:read"])
    client = await api_key_client(key=key)
    resp = await client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Acme",
            "stream": False,
        },
    )
    assert resp.status_code == 403, resp.text


async def test_chat_api_key_with_chat_write_scope_works(
    api_key: ApiKeyFactory,
    api_key_client: ApiKeyClientFactory,
    collection: CollectionFactory,
    document: DocumentFactory,
    admin_client: httpx.AsyncClient,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    key = await api_key(scopes=["chat:write"])
    client = await api_key_client(key=key)
    resp = await client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Acme",
            "stream": False,
        },
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Streaming chat
# ---------------------------------------------------------------------------


def _parse_sse_lines(lines: list[str]) -> list[dict[str, Any]]:
    """Parse raw streamed lines into a list of {event, data} dicts."""
    events: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for raw in lines:
        line = raw.rstrip("\n")
        if not line:
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current.setdefault("data_parts", []).append(line[len("data:") :].strip())
    if current:
        events.append(current)

    parsed: list[dict[str, Any]] = []
    for ev in events:
        data_text = "\n".join(ev.get("data_parts") or [])
        payload: Any = data_text
        if data_text and data_text != "[DONE]":
            try:
                payload = json.loads(data_text)
            except json.JSONDecodeError:
                payload = data_text
        parsed.append({"event": ev.get("event"), "data": payload})
    return parsed


async def test_chat_streaming_yields_deltas_and_completion(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    assert doc["status"] == "ready"
    await wait_until_searchable(admin_client, coll["name"], "Acme", top_k=3)

    raw_lines: list[str] = []
    async with admin_client.stream(
        "POST",
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "Who founded Acme Corp?",
            "stream": True,
        },
    ) as resp:
        if resp.status_code != 200:
            await resp.aread()
            raise AssertionError(f"expected 200 got {resp.status_code}: {resp.text}")
        assert "text/event-stream" in resp.headers.get("content-type", "")
        async for line in resp.aiter_lines():
            raw_lines.append(line + "\n")

    events = _parse_sse_lines(raw_lines)
    event_types = [e["event"] for e in events]
    assert "user_message" in event_types
    assert "sources" in event_types
    assert "delta" in event_types
    assert "assistant_message" in event_types
    assert "done" in event_types

    deltas = [e["data"]["delta"] for e in events if e["event"] == "delta"]
    accumulated = "".join(deltas)
    assert accumulated.strip()

    final = next(e for e in events if e["event"] == "assistant_message")
    assert final["data"]["content"] == accumulated


async def test_chat_streaming_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.post(
        "/v1/chat",
        json={"collection": "x", "message": "hi", "stream": True},
    )
    assert resp.status_code == 401, resp.text
