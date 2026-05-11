from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession, user_principal


def _key_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID(user_principal()["id"]),
        "name": "mcp:demo",
        "key_hash": "hash",
        "prefix": "rk_xxx",
        "permissions": {
            "mcp": {"title": "Demo", "server_name": "demo"},
            "scopes": ["collection:read"],
        },
        "active": True,
        "expires_at": None,
        "last_used_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class RefreshingSession(FakeSession):
    async def refresh(self, item):
        now = datetime.now(UTC)
        if not isinstance(getattr(item, "created_at", None), datetime):
            item.created_at = now
        if not isinstance(getattr(item, "updated_at", None), datetime):
            item.updated_at = now
        if getattr(item, "active", None) is None:
            item.active = True
        self.refreshed.append(item)


@pytest.fixture
def patch_mcp(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import mcp_servers

    async def noop(_h):
        return None

    monkeypatch.setattr(mcp_servers, "invalidate_api_key_principal", noop)
    monkeypatch.setattr(mcp_servers.audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(
        mcp_servers, "generate_api_key", lambda: ("plain-key", "rk_xxx", "new-hash")
    )


def test_list_mcp_servers_returns_user_owned(route_client) -> None:
    rows = [_key_row(), _key_row(name="mcp:b")]
    session = FakeSession(scalars_values=[rows])

    response = route_client(session=session).get("/v1/admin/mcp-servers")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_create_mcp_server_conflict_returns_409(route_client, patch_mcp) -> None:
    existing = _key_row()
    session = FakeSession(scalar_values=[existing])

    response = route_client(session=session).post(
        "/v1/admin/mcp-servers",
        json={"title": "Demo", "server_name": "demo"},
    )

    assert response.status_code == 409


def test_create_mcp_server_rejects_unknown_collection(route_client, patch_mcp) -> None:
    session = FakeSession(scalar_values=[None, None])

    response = route_client(session=session).post(
        "/v1/admin/mcp-servers",
        json={"title": "Demo", "server_name": "demo", "collection": "nope"},
    )

    assert response.status_code == 400


def test_create_mcp_server_happy_path(route_client, patch_mcp) -> None:
    session = RefreshingSession(scalar_values=[None, uuid.uuid4()])

    response = route_client(session=session).post(
        "/v1/admin/mcp-servers",
        json={"title": "Demo", "server_name": "demo", "collection": "docs"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["api_key"] == "plain-key"
    assert body["server_name"] == "demo"


def test_update_mcp_server_invalid_uuid(route_client) -> None:
    response = route_client().patch("/v1/admin/mcp-servers/not-uuid", json={"title": "x"})
    assert response.status_code == 404


def test_update_mcp_server_not_found(route_client) -> None:
    session = FakeSession(get_values={})
    response = route_client(session=session).patch(
        f"/v1/admin/mcp-servers/{uuid.uuid4()}", json={"title": "x"}
    )
    assert response.status_code == 404


def test_update_mcp_server_wrong_owner(route_client) -> None:
    key = _key_row(user_id=uuid.uuid4())
    session = FakeSession(get_values={key.id: key})

    response = route_client(session=session).patch(
        f"/v1/admin/mcp-servers/{key.id}", json={"title": "x"}
    )
    assert response.status_code == 404


def test_update_mcp_server_server_name_conflict(route_client, patch_mcp) -> None:
    me = user_principal()
    key = _key_row(user_id=uuid.UUID(me["id"]))
    other = _key_row(user_id=uuid.UUID(me["id"]), name="mcp:other")

    session = FakeSession(
        get_values={key.id: key},
        scalar_values=[other],
    )

    response = route_client(user=me, session=session).patch(
        f"/v1/admin/mcp-servers/{key.id}",
        json={"server_name": "taken"},
    )

    assert response.status_code == 409


def test_update_mcp_server_happy_path(route_client, patch_mcp) -> None:
    me = user_principal()
    key = _key_row(user_id=uuid.UUID(me["id"]))
    session = FakeSession(
        get_values={key.id: key},
        scalar_values=[None, uuid.uuid4()],
    )

    response = route_client(user=me, session=session).patch(
        f"/v1/admin/mcp-servers/{key.id}",
        json={
            "title": "Renamed",
            "server_name": "renamed",
            "collection": "docs",
        },
    )

    assert response.status_code == 200
    assert key.permissions["mcp"]["title"] == "Renamed"
    assert key.permissions["mcp"]["server_name"] == "renamed"
    assert key.permissions["collection"] == "docs"


def test_update_mcp_server_clears_collection_with_empty_string(route_client, patch_mcp) -> None:
    me = user_principal()
    key = _key_row(
        user_id=uuid.UUID(me["id"]),
        permissions={
            "mcp": {"title": "T", "server_name": "demo"},
            "collection": "docs",
        },
    )
    session = FakeSession(get_values={key.id: key})

    response = route_client(user=me, session=session).patch(
        f"/v1/admin/mcp-servers/{key.id}",
        json={"collection": ""},
    )

    assert response.status_code == 200
    assert "collection" not in key.permissions


def test_rotate_mcp_server_invalid_uuid(route_client) -> None:
    response = route_client().post("/v1/admin/mcp-servers/not-uuid/rotate")
    assert response.status_code == 404


def test_rotate_mcp_server_not_found(route_client) -> None:
    session = FakeSession(get_values={})
    response = route_client(session=session).post(f"/v1/admin/mcp-servers/{uuid.uuid4()}/rotate")
    assert response.status_code == 404


def test_rotate_mcp_server_happy_path(route_client, patch_mcp) -> None:
    me = user_principal()
    key = _key_row(user_id=uuid.UUID(me["id"]))
    session = FakeSession(get_values={key.id: key})

    response = route_client(user=me, session=session).post(f"/v1/admin/mcp-servers/{key.id}/rotate")

    assert response.status_code == 200
    assert response.json()["api_key"] == "plain-key"
    assert key.key_hash == "new-hash"


def test_delete_mcp_server_invalid_uuid(route_client) -> None:
    response = route_client().delete("/v1/admin/mcp-servers/not-uuid")
    assert response.status_code == 404


def test_delete_mcp_server_not_found(route_client) -> None:
    session = FakeSession(get_values={})
    response = route_client(session=session).delete(f"/v1/admin/mcp-servers/{uuid.uuid4()}")
    assert response.status_code == 404


def test_delete_mcp_server_happy_path(route_client, patch_mcp) -> None:
    me = user_principal()
    key = _key_row(user_id=uuid.UUID(me["id"]))
    session = FakeSession(get_values={key.id: key})

    response = route_client(user=me, session=session).delete(f"/v1/admin/mcp-servers/{key.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "MCP server deleted"
