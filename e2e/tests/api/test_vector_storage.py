"""End-to-end tests for bigrag.routers.admin_vector_storage.

Endpoints covered:
- GET /v1/admin/vector-storage/overview
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope


async def test_vector_storage_overview_requires_admin_session(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/admin/vector-storage/overview")
    assert resp.status_code == 401, resp.text


async def test_vector_storage_overview_rejects_api_key(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/vector-storage/overview")
    assert resp.status_code in (401, 403), resp.text


async def test_vector_storage_overview_returns_provider_shape(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/vector-storage/overview")
    body = assert_envelope(resp, 200)

    for key in ("fallback_provider", "configured_providers", "provider_health", "collections", "totals"):
        assert key in body, f"missing top-level key {key!r} in {body!r}"

    assert isinstance(body["fallback_provider"], str) and body["fallback_provider"]
    assert isinstance(body["configured_providers"], list)
    # bigRAG can return a fallback_provider label distinct from the listed
    # configured providers (e.g., "collection" when collection-level provider
    # overrides are in effect). Just assert the field is non-empty here.
    assert isinstance(body["provider_health"], dict)
    for provider in body["configured_providers"]:
        assert provider in body["provider_health"], (
            f"provider_health missing entry for {provider!r}"
        )

    assert isinstance(body["collections"], list)
    totals = body["totals"]
    for key in ("collections", "documents", "chunks", "bytes"):
        assert key in totals
        assert isinstance(totals[key], int)
    assert totals["collections"] == len(body["collections"])


async def test_vector_storage_overview_reflects_collection_changes(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    before = await admin_client.get("/v1/admin/vector-storage/overview")
    before_body = assert_envelope(before, 200)
    before_count = before_body["totals"]["collections"]
    before_names = {c["name"] for c in before_body["collections"]}

    new_coll = await collection()

    after = await admin_client.get("/v1/admin/vector-storage/overview")
    after_body = assert_envelope(after, 200)
    after_names = {c["name"] for c in after_body["collections"]}

    assert new_coll["name"] in after_names
    assert new_coll["name"] not in before_names
    assert after_body["totals"]["collections"] >= before_count + 1

    entry = next(c for c in after_body["collections"] if c["name"] == new_coll["name"])
    for key in ("name", "provider", "documents", "chunks", "bytes"):
        assert key in entry
    assert entry["documents"] == 0
    assert entry["chunks"] == 0
