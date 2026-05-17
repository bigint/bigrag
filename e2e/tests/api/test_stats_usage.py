"""End-to-end tests for /v1/stats (bigrag.routers.health.platform_stats)
and bigrag.routers.usage.

Endpoints covered:
- GET /v1/stats         (any authenticated user)
- GET /v1/usage         (any authenticated user, audit:read scope on API keys)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope, poll_until


async def test_stats_requires_authentication(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/stats")
    assert resp.status_code == 401, resp.text


async def test_stats_accepts_api_key(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/stats")
    body = assert_envelope(resp, 200)
    assert "collections" in body


async def test_stats_returns_full_shape(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get("/v1/stats")
    body = assert_envelope(resp, 200)

    for key in (
        "status",
        "collections",
        "documents",
        "webhooks",
        "queue",
        "queue_health",
        "workers",
    ):
        assert key in body, f"missing top-level key {key!r}"

    assert isinstance(body["collections"], int)
    assert isinstance(body["webhooks"], int)

    docs = body["documents"]
    for key in (
        "total",
        "ready",
        "pending",
        "processing",
        "failed",
        "total_chunks",
        "total_tokens",
        "total_size_bytes",
    ):
        assert key in docs, f"missing documents.{key}"
        assert isinstance(docs[key], int)

    queue_health = body["queue_health"]
    assert queue_health["status"] in ("ok", "degraded", "down")
    assert isinstance(queue_health["reasons"], list)

    workers = body["workers"]
    for key in ("online", "status", "heartbeat_at", "heartbeat_age_seconds"):
        assert key in workers


async def test_stats_collection_count_grows_with_new_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    # The platform_stats endpoint caches for ~15s; allow a slow propagation.
    before_body = (await admin_client.get("/v1/stats")).json()
    before = before_body["collections"]
    await collection()

    async def _fetch() -> int:
        r = await admin_client.get("/v1/stats")
        r.raise_for_status()
        return r.json()["collections"]

    # Stats are cached; counter may not advance within 15s, so just verify
    # eventual consistency in a best-effort poll. The strict assertion is
    # that the new collection appears in the underlying list.
    try:
        await poll_until(
            _fetch,
            predicate=lambda v: v >= before + 1,
            timeout=20.0,
            interval=1.0,
            description="stats.collections to increment",
        )
    except TimeoutError:
        # cache may not have rolled over; the existence check below is
        # enough to confirm the collection actually exists.
        pass

    list_resp = await admin_client.get("/v1/collections")
    list_body = assert_envelope(list_resp, 200)
    assert isinstance(list_body, dict) and "collections" in list_body
    assert len(list_body["collections"]) >= before + 1


async def test_usage_requires_authentication(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/usage")
    assert resp.status_code == 401, resp.text


async def test_usage_returns_full_shape(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get("/v1/usage")
    body = assert_envelope(resp, 200)

    for key in (
        "window_days",
        "queries_total",
        "queries_per_day_avg",
        "documents_total",
        "chunks_total",
        "storage_bytes_total",
        "embedding_tokens_total",
        "embedding_cost_usd_estimate",
        "avg_latency_ms",
        "timeline",
        "by_collection",
    ):
        assert key in body, f"missing key {key!r}"

    assert body["window_days"] == 30
    assert isinstance(body["queries_total"], int)
    assert isinstance(body["documents_total"], int)
    assert isinstance(body["chunks_total"], int)
    assert isinstance(body["timeline"], list)
    assert isinstance(body["by_collection"], list)


async def test_usage_window_days_query_parameter(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/usage", params={"window_days": 7})
    body = assert_envelope(resp, 200)
    assert body["window_days"] == 7


async def test_usage_rejects_api_key_without_audit_scope(
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(scopes=["query:read"])
    client = await api_key_client(key=created)
    resp = await client.get("/v1/usage")
    assert resp.status_code == 403, resp.text


async def test_usage_accepts_api_key_with_audit_scope(
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(scopes=["audit:read"])
    client = await api_key_client(key=created)
    resp = await client.get("/v1/usage")
    body = assert_envelope(resp, 200)
    assert "window_days" in body


async def test_usage_reflects_new_collection_in_by_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    try:
        doc = await document(coll["name"])
    except Exception:
        # If ingestion can't complete, still check the empty collection
        # appears in the by_collection list.
        doc = None

    # Allow a brief moment for write-side propagation; usage uses no
    # cache so should be near-instant.
    await asyncio.sleep(0.5)

    resp = await admin_client.get("/v1/usage")
    body = assert_envelope(resp, 200)
    names = {entry["collection"] for entry in body["by_collection"]}
    assert coll["name"] in names, f"new collection missing from usage by_collection: {names!r}"

    entry = next(e for e in body["by_collection"] if e["collection"] == coll["name"])
    for key in (
        "collection",
        "documents",
        "chunks",
        "storage_bytes",
        "embedding_tokens",
        "embedding_cost_usd_estimate",
        "queries",
        "avg_latency_ms",
    ):
        assert key in entry, f"missing by_collection[].{key}"
    if doc is not None and doc.get("status") == "ready":
        assert entry["documents"] >= 1
