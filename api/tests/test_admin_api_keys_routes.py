from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession, user_principal


def _key_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "test-key",
        "key_hash": "hash",
        "prefix": "rk_xxx",
        "permissions": {},
        "active": True,
        "expires_at": None,
        "last_used_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def patch_api_keys(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import admin_api_keys

    async def fake_invalidate(_hash):
        return None

    monkeypatch.setattr(admin_api_keys, "invalidate_api_key_principal", fake_invalidate)
    monkeypatch.setattr(admin_api_keys.audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(admin_api_keys, "generate_api_key", lambda: ("plain-key", "rk_xxx", "hash"))


def test_list_api_keys_requires_admin(route_client) -> None:
    response = route_client(user=user_principal(role="member")).get("/v1/admin/api-keys")

    assert response.status_code == 403


def test_list_api_keys_returns_paginated(route_client) -> None:
    keys = [_key_row(name="a"), _key_row(name="b", permissions={"scopes": ["query.read"]})]
    session = FakeSession(scalars_values=[keys], scalar_values=[2])

    response = route_client(session=session).get("/v1/admin/api-keys?limit=5")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_create_api_key_rejects_invalid_scopes(route_client, patch_api_keys) -> None:
    response = route_client().post(
        "/v1/admin/api-keys",
        json={"name": "k", "scopes": ["invalid-scope"]},
    )

    assert response.status_code == 400


def test_create_api_key_rejects_unknown_collection(route_client, patch_api_keys) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).post(
        "/v1/admin/api-keys",
        json={"name": "k", "collection": "nope"},
    )

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]


def test_create_api_key_happy_path(route_client, patch_api_keys) -> None:
    class RefreshingSession(FakeSession):
        async def refresh(self, item):
            item.created_at = datetime.now(UTC)
            item.updated_at = datetime.now(UTC)
            if getattr(item, "active", None) is None:
                item.active = True
            self.refreshed.append(item)

    session = RefreshingSession(scalar_values=[uuid.uuid4()])

    response = route_client(session=session).post(
        "/v1/admin/api-keys",
        json={"name": "k", "collection": "docs"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "plain-key"
    assert body["prefix"] == "rk_xxx"


def test_update_api_key_invalid_uuid(route_client) -> None:
    response = route_client().patch("/v1/admin/api-keys/not-uuid", json={"name": "x"})

    assert response.status_code == 404


def test_update_api_key_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).patch(
        f"/v1/admin/api-keys/{uuid.uuid4()}", json={"name": "x"}
    )

    assert response.status_code == 404


def test_update_api_key_blocks_mcp_keys(route_client) -> None:
    key = _key_row(permissions={"mcp": {"endpoint": "ep"}})
    session = FakeSession(get_values={key.id: key})

    response = route_client(session=session).patch(
        f"/v1/admin/api-keys/{key.id}", json={"name": "x"}
    )

    assert response.status_code == 404


def test_update_api_key_happy_path(route_client, patch_api_keys) -> None:
    key = _key_row(permissions={"scopes": ["query.read"], "collection": "old"})
    session = FakeSession(
        get_values={key.id: key},
        scalar_values=[uuid.uuid4()],
    )

    response = route_client(session=session).patch(
        f"/v1/admin/api-keys/{key.id}",
        json={
            "name": "renamed",
            "active": False,
            "scopes": [],
            "collection": "docs",
        },
    )

    assert response.status_code == 200
    assert key.name == "renamed"
    assert key.active is False
    assert "scopes" not in key.permissions
    assert key.permissions["collection"] == "docs"


def test_delete_api_key_invalid_uuid(route_client) -> None:
    response = route_client().delete("/v1/admin/api-keys/not-uuid")

    assert response.status_code == 404


def test_delete_api_key_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).delete(
        f"/v1/admin/api-keys/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_delete_api_key_blocks_mcp(route_client) -> None:
    key = _key_row(permissions={"mcp": {"x": True}})
    session = FakeSession(get_values={key.id: key})

    response = route_client(session=session).delete(f"/v1/admin/api-keys/{key.id}")

    assert response.status_code == 404


def test_delete_api_key_happy_path(route_client, patch_api_keys) -> None:
    key = _key_row()
    session = FakeSession(get_values={key.id: key})

    response = route_client(session=session).delete(f"/v1/admin/api-keys/{key.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "API key deleted"
