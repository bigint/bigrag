"""Cross-router error-case smoke tests.

These tests intentionally cover *generic* error paths and authorization
edges rather than duplicating router-specific 422 cases written by other
agents.

Status codes exercised:
- 401 missing auth
- 403 wrong scope
- 404 unknown resource (collection / document / user / webhook)
- 409 duplicate collection name
- 413 oversized upload
- 422 malformed JSON / missing required fields / bad enum value

We deliberately *do not* trigger any path that may legitimately 500 —
any 500 surfaced here is a bug; if you see one please add a comment in
the test and report it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import unique_name


# ---------------------------------------------------------------------------
# 401 — missing authentication on a protected endpoint.
# ---------------------------------------------------------------------------


async def test_401_collections_list_without_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/collections")
    assert resp.status_code == 401, resp.text


async def test_401_admin_users_without_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/admin/users")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 403 — wrong scope on an API key.
# ---------------------------------------------------------------------------


async def test_403_api_key_documents_read_cannot_upload(
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    created = await api_key(scopes=["document:read"])
    client = await api_key_client(key=created)
    files = {"file": ("x.txt", b"hello", "application/octet-stream")}
    resp = await client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code == 403, resp.text


async def test_403_api_key_cannot_hit_admin_endpoints(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    # /v1/admin/users requires an admin *session*; an API key is rejected
    # by require_session before any scope check.
    resp = await client.get("/v1/admin/users")
    assert resp.status_code in (401, 403), resp.text


# ---------------------------------------------------------------------------
# 404 — unknown identifiers.
# ---------------------------------------------------------------------------


async def test_404_unknown_collection(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get(f"/v1/collections/{unique_name('nope')}")
    assert resp.status_code == 404, resp.text


async def test_404_unknown_document(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


async def test_404_unknown_user(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.delete(
        "/v1/admin/users/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


async def test_404_unknown_webhook(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get(
        "/v1/admin/webhooks/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 409 — duplicate collection name.
# ---------------------------------------------------------------------------


async def test_409_duplicate_collection_name(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    first = await collection()
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": first["name"],
            "description": "dup attempt",
            "vector_store_provider": "qdrant",
            "chunk_size": 512,
            "chunk_overlap": 50,
            "chunk_strategy": "paragraph",
            "reranking_enabled": False,
            "default_top_k": 10,
            "default_search_mode": "semantic",
        },
    )
    assert resp.status_code == 409, resp.text


# ---------------------------------------------------------------------------
# 413 — oversized upload (>64 MiB by default).
# ---------------------------------------------------------------------------


async def test_413_oversized_upload(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    # 65 MiB; the default ``max_upload_size_mb`` is 64.
    huge = b"x" * (65 * 1024 * 1024)
    # Use a supported extension so the request is rejected for *size*,
    # not for an unsupported file type before the size check fires.
    files = {"file": ("big.txt", huge, "text/plain")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code in (400, 413, 422), (
        f"expected 4xx for oversized upload, got {resp.status_code}: {resp.text[:300]}"
    )


# ---------------------------------------------------------------------------
# 422 — malformed JSON, missing required field, bad enum.
# ---------------------------------------------------------------------------


async def test_422_malformed_json(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        content=b"{not-json:",
        headers={"Content-Type": "application/json", "Origin": "http://localhost:4000"},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_422_missing_required_field_on_create_collection(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={},  # ``name`` is required
    )
    assert resp.status_code == 422, resp.text


async def test_422_bad_enum_on_create_collection(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": unique_name("enum"),
            "vector_store_provider": "not-a-real-provider",
            "chunk_strategy": "paragraph",
            "default_search_mode": "semantic",
        },
    )
    assert resp.status_code == 422, resp.text


async def test_422_wrong_type_on_create_collection(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": unique_name("badtype"),
            "chunk_size": "not-an-int",
        },
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 422 on out-of-range query params.
# ---------------------------------------------------------------------------


async def test_422_out_of_range_pagination(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        "/v1/admin/api-keys", params={"limit": 0}
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Sanity: a 500 from any of the above would be a bug. Re-run the most
# suspicious malformed-JSON case and assert it is *not* a 500.
# ---------------------------------------------------------------------------


async def test_no_500_on_garbage_body(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        content=b"\x00\xff\x00\xff",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code < 500, (
        f"server should not 500 on garbage body, got {resp.status_code}: {resp.text[:300]}"
    )
