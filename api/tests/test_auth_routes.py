from __future__ import annotations

from conftest import FakeSession, now, row, user_principal


def test_setup_status_reads_user_count(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[0]))

    assert client.get("/v1/auth/setup-status").json() == {"needs_setup": True}


def test_whoami_returns_api_key_principal(route_client) -> None:
    user = user_principal(
        auth_method="api_key",
        api_key_id="123",
        api_key_name="worker",
        scopes=["collection:read"],
        collection="docs",
    )
    client = route_client(user=user)

    assert client.get("/v1/auth/whoami").json() == {
        "authenticated": True,
        "auth_method": "api_key",
        "user_id": user["id"],
        "user_email": user["email"],
        "api_key_id": "123",
        "api_key_name": "worker",
        "scopes": ["collection:read"],
        "collection": "docs",
    }


def test_session_only_route_rejects_api_key(route_client) -> None:
    client = route_client(
        user=user_principal(auth_method="api_key"),
        session=FakeSession(),
    )

    response = client.post(
        "/v1/auth/password",
        json={"current_password": "old", "new_password": "new-password"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Session authentication required"


def test_me_returns_session_user(route_client) -> None:
    user_id = "00000000-0000-0000-0000-000000000001"
    db_user = row(
        id=user_id,
        email="admin@example.com",
        display_name="Admin",
        role="admin",
        last_login_at=None,
        created_at=now(),
        updated_at=now(),
    )
    client = route_client(
        user=user_principal(id=user_id),
        session=FakeSession(get_values={user_id: db_user}),
    )

    response = client.get("/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@example.com"
