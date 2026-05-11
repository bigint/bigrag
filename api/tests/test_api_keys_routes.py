from __future__ import annotations

import uuid

from conftest import FakeSession, now, row, user_principal


def api_key_row(**overrides):
    value = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "worker",
        "key_hash": "hash",
        "prefix": "ragc_sk_test",
        "active": True,
        "permissions": {"scopes": ["collection:read"], "collection": "docs"},
        "last_used_at": None,
        "expires_at": None,
        "created_at": now(),
        "updated_at": now(),
    }
    value.update(overrides)
    return row(**value)


def test_list_api_keys_masks_secret_material(route_client) -> None:
    client = route_client(
        session=FakeSession(
            scalar_values=[1],
            scalars_values=[[api_key_row()]],
        )
    )

    response = client.get("/v1/admin/api-keys")

    assert response.status_code == 200
    payload = response.json()["keys"][0]
    assert payload["prefix"] == "ragc_sk_test"
    assert "key" not in payload
    assert "key_hash" not in payload


def test_create_api_key_rejects_invalid_scope(route_client) -> None:
    response = route_client().post(
        "/v1/admin/api-keys",
        json={"name": "bad", "scopes": ["nope"]},
    )

    assert response.status_code == 400
    assert "resource:action" in response.json()["detail"]


def test_delete_api_key_requires_admin_session(route_client) -> None:
    response = route_client(user=user_principal(role="member")).delete(
        f"/v1/admin/api-keys/{uuid.uuid4()}"
    )

    assert response.status_code == 403
