"""End-to-end tests for bigrag.routers.admin_api_keys.

Endpoints covered:
- POST   /v1/admin/api-keys
- GET    /v1/admin/api-keys
- PATCH  /v1/admin/api-keys/{id}
- POST   /v1/admin/api-keys/{id}/rotate
- DELETE /v1/admin/api-keys/{id}
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tests._helpers import assert_envelope, unique_name


async def test_create_api_key_returns_plaintext_only_on_create(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    created = await api_key(name=unique_name("e2e-key"))
    assert created["key"].startswith("bigrag_sk_")
    assert created["prefix"]
    assert created["active"] is True
    assert created["scopes"] == []
    assert created["collection"] is None

    list_resp = await admin_client.get("/v1/admin/api-keys")
    body = assert_envelope(list_resp, 200)
    found = next((k for k in body["keys"] if k["id"] == created["id"]), None)
    assert found is not None
    assert "key" not in found, "list response must not include plaintext key"


async def test_list_api_keys_pagination(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    await api_key(name=unique_name("page"))
    await api_key(name=unique_name("page"))
    resp = await admin_client.get(
        "/v1/admin/api-keys",
        params={"limit": 1, "offset": 0, "include_total": "true"},
    )
    body = assert_envelope(resp, 200)
    assert len(body["keys"]) == 1
    assert body["total"] >= 2


async def test_create_api_key_with_scopes_and_collection(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    created = await api_key(
        name=unique_name("pinned"),
        scopes=["query:read"],
        collection=coll["name"],
    )
    assert created["scopes"] == ["query:read"]
    assert created["collection"] == coll["name"]


async def test_patch_api_key_rename_and_deactivate(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(name=unique_name("orig"))
    new_name = unique_name("renamed")
    resp = await admin_client.patch(
        f"/v1/admin/api-keys/{created['id']}",
        json={"name": new_name, "active": False},
    )
    body = assert_envelope(resp, 200)
    assert body["name"] == new_name
    assert body["active"] is False

    client = await api_key_client(key=created)
    probe = await client.get("/v1/auth/whoami")
    assert probe.status_code == 401, probe.text


async def test_patch_api_key_set_expires_at(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(name=unique_name("exp"))
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    resp = await admin_client.patch(
        f"/v1/admin/api-keys/{created['id']}",
        json={"expires_at": past},
    )
    assert_envelope(resp, 200)

    client = await api_key_client(key=created)
    probe = await client.get("/v1/auth/whoami")
    assert probe.status_code == 401, probe.text


async def test_rotate_returns_new_secret_and_old_secret_dies(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(name=unique_name("rotate"))
    old_secret = created["key"]

    old_client = await api_key_client(key=created)
    assert (await old_client.get("/v1/auth/whoami")).status_code == 200

    resp = await admin_client.post(f"/v1/admin/api-keys/{created['id']}/rotate")
    body = assert_envelope(resp, 200)
    new_secret = body["key"]
    assert new_secret.startswith("bigrag_sk_")
    assert new_secret != old_secret

    old_probe = await old_client.get("/v1/auth/whoami")
    assert old_probe.status_code == 401, old_probe.text

    new_client = await api_key_client(key={"id": created["id"], "key": new_secret})
    assert (await new_client.get("/v1/auth/whoami")).status_code == 200


async def test_delete_api_key_stops_working(
    admin_client: httpx.AsyncClient,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    created = await api_key(name=unique_name("delete"))
    client = await api_key_client(key=created)
    assert (await client.get("/v1/auth/whoami")).status_code == 200

    resp = await admin_client.delete(f"/v1/admin/api-keys/{created['id']}")
    assert_envelope(resp, 200)

    probe = await client.get("/v1/auth/whoami")
    assert probe.status_code == 401, probe.text


async def test_collection_pinned_key_403_on_other_collection(
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    other = await collection()
    created = await api_key(
        name=unique_name("pin403"),
        collection=pinned["name"],
    )
    client = await api_key_client(key=created)

    own = await client.get(f"/v1/collections/{pinned['name']}")
    assert own.status_code == 200, own.text

    foreign = await client.get(f"/v1/collections/{other['name']}")
    assert foreign.status_code == 403, foreign.text


async def test_scope_limited_key_blocks_document_upload(
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    created = await api_key(
        name=unique_name("queryonly"),
        scopes=["query:read"],
    )
    client = await api_key_client(key=created)
    files = {"file": ("a.txt", b"hello", "application/octet-stream")}
    resp = await client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code == 403, resp.text


async def test_patch_api_key_invalid_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.patch(
        "/v1/admin/api-keys/not-a-uuid",
        json={"name": "x"},
    )
    assert resp.status_code == 404, resp.text


async def test_delete_api_key_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.delete(
        "/v1/admin/api-keys/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text
