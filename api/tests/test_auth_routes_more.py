from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession, user_principal


def _user_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "email": "u@example.com",
        "password_hash": "$argon2id$hash",
        "display_name": "Member",
        "role": "admin",
        "last_login_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def patch_auth(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import auth

    async def fake_cookie_opts(_keys):
        return {
            "session_cookie_secure": False,
            "session_cookie_samesite": "lax",
            "session_cookie_domain": None,
        }

    async def noop():
        return None

    async def noop_token(_hash):
        return None

    monkeypatch.setattr(auth, "get_values", fake_cookie_opts)
    monkeypatch.setattr(auth, "invalidate_session_principal", noop_token)
    monkeypatch.setattr(auth, "invalidate_auth_principals", noop)
    monkeypatch.setattr(auth, "generate_session_token", lambda: "tok")
    monkeypatch.setattr(auth, "hash_session_token", lambda t: f"h:{t}")
    monkeypatch.setattr(auth, "hash_password", lambda p: f"hash:{p}")
    monkeypatch.setattr(auth, "verify_password", lambda p, _h: p == "correctpw")
    monkeypatch.setattr(auth, "needs_rehash", lambda _h: False)
    monkeypatch.setattr(auth.audit, "record", lambda *a, **k: None)


def test_setup_status_signals_needs_setup_when_no_users(route_client) -> None:
    session = FakeSession(scalar_values=[0])

    response = route_client(session=session, unauthenticated=True).get("/v1/auth/setup-status")

    assert response.status_code == 200
    assert response.json()["needs_setup"] is True


def test_setup_returns_409_after_setup_done(route_client, patch_auth) -> None:
    session = FakeSession(scalar_values=[1])

    response = route_client(session=session, unauthenticated=True).post(
        "/v1/auth/setup",
        json={
            "email": "a@example.com",
            "password": "longpassword",
            "display_name": "Admin",
        },
    )

    assert response.status_code == 409


class _RefreshingSession(FakeSession):
    async def refresh(self, item):
        now = datetime.now(UTC)
        if not isinstance(getattr(item, "created_at", None), datetime):
            item.created_at = now
        if not isinstance(getattr(item, "updated_at", None), datetime):
            item.updated_at = now
        if not isinstance(getattr(item, "last_login_at", None), datetime):
            item.last_login_at = now
        self.refreshed.append(item)


def test_setup_creates_first_admin(route_client, monkeypatch, patch_auth) -> None:
    session = _RefreshingSession(scalar_values=[0])

    response = route_client(session=session, unauthenticated=True).post(
        "/v1/auth/setup",
        json={
            "email": "a@example.com",
            "password": "longpassword",
            "display_name": "Admin",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "a@example.com"


def test_login_unknown_user_returns_401(route_client, patch_auth) -> None:
    session = _RefreshingSession(scalar_values=[None])

    response = route_client(session=session, unauthenticated=True).post(
        "/v1/auth/login",
        json={"email": "missing@example.com", "password": "correctpw"},
    )

    assert response.status_code == 401


def test_login_bad_password_returns_401(route_client, patch_auth) -> None:
    user = _user_row()
    session = _RefreshingSession(scalar_values=[user])

    response = route_client(session=session, unauthenticated=True).post(
        "/v1/auth/login",
        json={"email": user.email, "password": "wrongpwxx"},
    )

    assert response.status_code == 401


def test_login_happy_path_sets_cookie(route_client, patch_auth) -> None:
    user = _user_row()
    session = _RefreshingSession(scalar_values=[user])

    response = route_client(session=session, unauthenticated=True).post(
        "/v1/auth/login",
        json={"email": user.email, "password": "correctpw"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == user.email


def test_logout_clears_cookie_without_session(route_client, patch_auth) -> None:
    response = route_client(unauthenticated=True).post("/v1/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out"


def test_logout_with_cookie_records_audit(route_client, monkeypatch, patch_auth) -> None:
    from bigrag.config import settings

    user = _user_row()
    session = _RefreshingSession(scalar_values=[user])
    client = route_client(session=session, unauthenticated=True)
    client.cookies.set(settings.session_cookie_name, "the-token")

    response = client.post(
        "/v1/auth/logout",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200


def test_logout_all_rejects_api_key_auth(route_client) -> None:
    response = route_client(user=user_principal(auth_method="api_key")).post("/v1/auth/logout-all")

    assert response.status_code == 403


def test_logout_all_happy_path(route_client, patch_auth) -> None:
    response = route_client().post("/v1/auth/logout-all")

    assert response.status_code == 200
    assert response.json()["message"] == "Signed out of all devices"


def test_me_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).get("/v1/auth/me")

    assert response.status_code == 404


def test_me_happy_path(route_client) -> None:
    me = user_principal()
    user = _user_row(id=uuid.UUID(me["id"]), email=me["email"])
    session = FakeSession(get_values={user.id: user})

    response = route_client(user=me, session=session).get("/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == me["email"]


def test_whoami_returns_principal(route_client) -> None:
    response = route_client().get("/v1/auth/whoami")

    assert response.status_code == 200
    assert response.json()["auth_method"] == "session"


def test_change_password_rejects_wrong_current(route_client, patch_auth) -> None:
    user = _user_row()
    session = FakeSession(get_values={user.id: user})
    me = user_principal(id=str(user.id))

    response = route_client(user=me, session=session).post(
        "/v1/auth/password",
        json={"current_password": "wrongone", "new_password": "newlongpw"},
    )

    assert response.status_code == 401


def test_change_password_happy_path(route_client, patch_auth) -> None:
    user = _user_row()
    session = FakeSession(get_values={user.id: user})
    me = user_principal(id=str(user.id))

    response = route_client(user=me, session=session).post(
        "/v1/auth/password",
        json={"current_password": "correctpw", "new_password": "newlongpw"},
    )

    assert response.status_code == 200
    assert user.password_hash == "hash:newlongpw"
