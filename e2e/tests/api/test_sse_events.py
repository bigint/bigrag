"""End-to-end tests for the SSE event-stream endpoints on collections.

Endpoints covered (bigrag.routers.collections):
- GET  /v1/collections/{name}/events           (SSE, session OR ?token=)
- POST /v1/collections/{name}/events/token     (mint short-lived token)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import (
    CollectionFactory,
    assert_envelope,
    read_fixture,
    unique_name,
)


def _parse_sse_data(raw_block: str) -> list[dict[str, Any]]:
    """Pull every ``data: {...}`` line in a single SSE chunk into dicts."""
    events: list[dict[str, Any]] = []
    for line in raw_block.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


async def _collect_events(
    client: httpx.AsyncClient,
    path: str,
    *,
    until: Callable[[dict[str, Any]], bool],
    timeout: float = 30.0,
    params: dict[str, str] | None = None,
    triggers: list[Callable[[], Awaitable[Any]]] | None = None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []

    async def _read() -> None:
        async with client.stream("GET", path, params=params or None) as resp:
            assert resp.status_code == 200, await resp.aread()
            assert "text/event-stream" in resp.headers.get("content-type", "")
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, _, buffer = buffer.partition("\n\n")
                    for event in _parse_sse_data(block):
                        collected.append(event)
                        if until(event):
                            return

    reader = asyncio.create_task(_read())
    try:
        if triggers:
            await asyncio.sleep(0.2)  # let the subscriber attach
            for trigger in triggers:
                await trigger()
        await asyncio.wait_for(reader, timeout=timeout)
    except asyncio.TimeoutError as exc:
        reader.cancel()
        raise TimeoutError(
            f"SSE stream {path!r} did not satisfy predicate within {timeout}s; "
            f"received {collected!r}"
        ) from exc
    return collected


# ---------------------------------------------------------------------------
# POST /v1/collections/{name}/events/token
# ---------------------------------------------------------------------------


async def test_events_token_returns_token_and_ttl(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(f"/v1/collections/{coll['name']}/events/token")
    body = assert_envelope(resp, 200)
    assert body["token"]
    assert isinstance(body["token"], str)
    assert isinstance(body["expires_in"], int)
    assert body["expires_in"] > 0


async def test_events_token_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.post(f"/v1/collections/{coll['name']}/events/token")
    assert resp.status_code == 401, resp.text


async def test_events_token_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        f"/v1/collections/{unique_name('missing')}/events/token"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# GET /v1/collections/{name}/events
# ---------------------------------------------------------------------------


async def test_events_stream_emits_connected_event(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    events = await _collect_events(
        admin_client,
        f"/v1/collections/{coll['name']}/events",
        until=lambda e: e.get("step") == "connected",
        timeout=10.0,
    )
    assert events, events
    first = events[0]
    assert first["step"] == "connected"
    assert first["status"] == "connected"
    assert coll["name"] in first["message"]


async def test_events_stream_receives_ingestion_progress(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()

    async def _upload() -> None:
        files = {"file": ("sample.txt", read_fixture("sample.txt"), "application/octet-stream")}
        resp = await admin_client.post(
            f"/v1/collections/{coll['name']}/documents",
            files=files,
        )
        assert resp.status_code == 201, resp.text

    events = await _collect_events(
        admin_client,
        f"/v1/collections/{coll['name']}/events",
        until=lambda e: e.get("status") in {"complete", "ready", "failed"},
        timeout=60.0,
        triggers=[_upload],
    )

    statuses = {e.get("status") for e in events}
    assert "connected" in statuses
    terminal = {"complete", "ready", "failed"}
    assert statuses & terminal, events
    document_events = [e for e in events if e.get("document_id")]
    assert document_events, events


async def test_events_stream_requires_auth_without_token(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.get(
        f"/v1/collections/{coll['name']}/events"
    )
    assert resp.status_code == 401, resp.text


async def test_events_stream_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        f"/v1/collections/{unique_name('missing')}/events"
    )
    assert resp.status_code == 404, resp.text


async def test_events_stream_token_grants_anonymous_access(
    admin_client: httpx.AsyncClient,
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    token_resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/events/token"
    )
    token_body = assert_envelope(token_resp, 200)
    token = token_body["token"]

    events = await _collect_events(
        unauth_client,
        f"/v1/collections/{coll['name']}/events",
        until=lambda e: e.get("step") == "connected",
        timeout=10.0,
        params={"token": token},
    )
    assert events
    assert events[0]["step"] == "connected"


async def test_events_stream_rejects_bad_token(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.get(
        f"/v1/collections/{coll['name']}/events",
        params={"token": "not-a-real-token"},
    )
    assert resp.status_code == 401, resp.text
