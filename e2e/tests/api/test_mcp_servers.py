"""End-to-end tests for bigrag.routers.mcp_servers.

Endpoints covered:
- GET    /v1/admin/mcp-servers
- POST   /v1/admin/mcp-servers
- PATCH  /v1/admin/mcp-servers/{server_id}
- POST   /v1/admin/mcp-servers/{server_id}/rotate
- DELETE /v1/admin/mcp-servers/{server_id}
"""

from __future__ import annotations

import uuid

import httpx

from tests._helpers import assert_envelope, unique_name


def _server_name() -> str:
    return f"mcp-{uuid.uuid4().hex[:8]}"


async def _create(
    admin_client: httpx.AsyncClient,
    *,
    title: str | None = None,
    server_name: str | None = None,
    collection: str | None = None,
) -> dict:
    body: dict = {
        "title": title or unique_name("mcp"),
        "server_name": server_name or _server_name(),
    }
    if collection is not None:
        body["collection"] = collection
    resp = await admin_client.post("/v1/admin/mcp-servers", json=body)
    return assert_envelope(resp, 201)


async def _cleanup(admin_client: httpx.AsyncClient, server_id: str) -> None:
    try:
        await admin_client.delete(f"/v1/admin/mcp-servers/{server_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Authz
# ---------------------------------------------------------------------------


async def test_list_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/admin/mcp-servers")
    assert resp.status_code == 401


async def test_list_rejects_api_key(api_key_client) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/mcp-servers")
    assert resp.status_code in (401, 403)


async def test_create_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.post(
        "/v1/admin/mcp-servers",
        json={"title": "x", "server_name": _server_name()},
    )
    assert resp.status_code == 401


async def test_patch_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.patch(
        f"/v1/admin/mcp-servers/{uuid.uuid4()}",
        json={"title": "x"},
    )
    assert resp.status_code == 401


async def test_rotate_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.post(f"/v1/admin/mcp-servers/{uuid.uuid4()}/rotate")
    assert resp.status_code == 401


async def test_delete_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.delete(f"/v1/admin/mcp-servers/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def test_create_returns_plaintext_api_key(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create(admin_client, title="Demo MCP")
    try:
        assert created["api_key"].startswith("bigrag_sk_")
        assert created["title"] == "Demo MCP"
        assert created["key_prefix"]
        assert created["key_active"] is True
        assert created["collection"] is None
    finally:
        await _cleanup(admin_client, created["id"])


async def test_create_with_collection_pins(
    admin_client: httpx.AsyncClient,
    collection,
) -> None:
    coll = await collection()
    created = await _create(admin_client, collection=coll["name"])
    try:
        assert created["collection"] == coll["name"]
    finally:
        await _cleanup(admin_client, created["id"])


async def test_create_with_unknown_collection_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/mcp-servers",
        json={
            "title": "nope",
            "server_name": _server_name(),
            "collection": "definitely-does-not-exist",
        },
    )
    assert resp.status_code in (400, 404), resp.text


async def test_create_duplicate_server_name_returns_409(
    admin_client: httpx.AsyncClient,
) -> None:
    name = _server_name()
    created = await _create(admin_client, server_name=name)
    try:
        resp = await admin_client.post(
            "/v1/admin/mcp-servers",
            json={"title": "again", "server_name": name},
        )
        assert resp.status_code == 409
    finally:
        await _cleanup(admin_client, created["id"])


async def test_create_invalid_server_name_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/mcp-servers",
        json={"title": "x", "server_name": "Invalid Name With Spaces"},
    )
    assert resp.status_code == 422


async def test_create_missing_title_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/mcp-servers",
        json={"server_name": _server_name()},
    )
    assert resp.status_code == 422


async def test_list_returns_created_server(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create(admin_client)
    try:
        resp = await admin_client.get("/v1/admin/mcp-servers")
        body = assert_envelope(resp, 200)
        ids = {s["id"] for s in body["servers"]}
        assert created["id"] in ids
        assert body["total"] == len(body["servers"])
        for server in body["servers"]:
            assert "api_key" not in server
    finally:
        await _cleanup(admin_client, created["id"])


async def test_patch_updates_title(admin_client: httpx.AsyncClient) -> None:
    created = await _create(admin_client, title="Original")
    try:
        resp = await admin_client.patch(
            f"/v1/admin/mcp-servers/{created['id']}",
            json={"title": "Renamed"},
        )
        body = assert_envelope(resp, 200)
        assert body["title"] == "Renamed"
    finally:
        await _cleanup(admin_client, created["id"])


async def test_patch_updates_server_name(admin_client: httpx.AsyncClient) -> None:
    created = await _create(admin_client)
    try:
        new_name = _server_name()
        resp = await admin_client.patch(
            f"/v1/admin/mcp-servers/{created['id']}",
            json={"server_name": new_name},
        )
        body = assert_envelope(resp, 200)
        assert body["server_name"] == new_name
    finally:
        await _cleanup(admin_client, created["id"])


async def test_patch_clears_collection_with_empty_string(
    admin_client: httpx.AsyncClient,
    collection,
) -> None:
    coll = await collection()
    created = await _create(admin_client, collection=coll["name"])
    try:
        resp = await admin_client.patch(
            f"/v1/admin/mcp-servers/{created['id']}",
            json={"collection": ""},
        )
        body = assert_envelope(resp, 200)
        assert body["collection"] is None
    finally:
        await _cleanup(admin_client, created["id"])


async def test_patch_pins_to_collection(
    admin_client: httpx.AsyncClient,
    collection,
) -> None:
    coll = await collection()
    created = await _create(admin_client)
    try:
        resp = await admin_client.patch(
            f"/v1/admin/mcp-servers/{created['id']}",
            json={"collection": coll["name"]},
        )
        body = assert_envelope(resp, 200)
        assert body["collection"] == coll["name"]
    finally:
        await _cleanup(admin_client, created["id"])


async def test_patch_404_for_unknown(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.patch(
        f"/v1/admin/mcp-servers/{uuid.uuid4()}",
        json={"title": "x"},
    )
    assert resp.status_code == 404

    resp = await admin_client.patch(
        "/v1/admin/mcp-servers/not-a-uuid",
        json={"title": "x"},
    )
    assert resp.status_code == 404


async def test_patch_duplicate_server_name_409(
    admin_client: httpx.AsyncClient,
) -> None:
    first = await _create(admin_client)
    second = await _create(admin_client)
    try:
        resp = await admin_client.patch(
            f"/v1/admin/mcp-servers/{second['id']}",
            json={"server_name": first["server_name"]},
        )
        assert resp.status_code == 409
    finally:
        await _cleanup(admin_client, first["id"])
        await _cleanup(admin_client, second["id"])


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------


async def test_rotate_returns_new_key(admin_client: httpx.AsyncClient) -> None:
    created = await _create(admin_client)
    try:
        resp = await admin_client.post(
            f"/v1/admin/mcp-servers/{created['id']}/rotate"
        )
        body = assert_envelope(resp, 200)
        assert body["api_key"].startswith("bigrag_sk_")
        assert body["api_key"] != created["api_key"]
        assert body["key_prefix"] != created["key_prefix"]
        assert body["id"] == created["id"]
    finally:
        await _cleanup(admin_client, created["id"])


async def test_rotated_old_key_no_longer_authenticates(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await _create(admin_client)
    try:
        old_token = created["api_key"]

        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            timeout=10.0,
            headers={"Authorization": f"Bearer {old_token}"},
        ) as old_client:
            resp = await old_client.get("/v1/collections")
            assert resp.status_code == 200

        rotated = (
            await admin_client.post(f"/v1/admin/mcp-servers/{created['id']}/rotate")
        ).json()

        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            timeout=10.0,
            headers={"Authorization": f"Bearer {old_token}"},
        ) as old_client:
            resp = await old_client.get("/v1/collections")
            assert resp.status_code in (401, 403)

        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            timeout=10.0,
            headers={"Authorization": f"Bearer {rotated['api_key']}"},
        ) as new_client:
            resp = await new_client.get("/v1/collections")
            assert resp.status_code == 200
    finally:
        await _cleanup(admin_client, created["id"])


async def test_rotate_404_for_unknown(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.post(f"/v1/admin/mcp-servers/{uuid.uuid4()}/rotate")
    assert resp.status_code == 404

    resp = await admin_client.post("/v1/admin/mcp-servers/not-a-uuid/rotate")
    assert resp.status_code == 404


async def test_rotate_does_not_apply_to_regular_api_keys(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    key = await api_key()
    resp = await admin_client.post(f"/v1/admin/mcp-servers/{key['id']}/rotate")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_removes_server(admin_client: httpx.AsyncClient) -> None:
    created = await _create(admin_client)
    resp = await admin_client.delete(f"/v1/admin/mcp-servers/{created['id']}")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"

    listing = (await admin_client.get("/v1/admin/mcp-servers")).json()
    ids = {s["id"] for s in listing["servers"]}
    assert created["id"] not in ids


async def test_delete_404_for_unknown(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.delete(f"/v1/admin/mcp-servers/{uuid.uuid4()}")
    assert resp.status_code == 404

    resp = await admin_client.delete("/v1/admin/mcp-servers/not-a-uuid")
    assert resp.status_code == 404


async def test_delete_does_not_apply_to_regular_api_keys(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    key = await api_key()
    resp = await admin_client.delete(f"/v1/admin/mcp-servers/{key['id']}")
    assert resp.status_code == 404
