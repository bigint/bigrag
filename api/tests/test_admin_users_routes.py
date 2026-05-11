from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from asyncpg.exceptions import UniqueViolationError
from conftest import FakeSession, user_principal
from sqlalchemy.exc import IntegrityError


def _user_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "email": "u@example.com",
        "password_hash": "$argon2id$...",
        "display_name": "Member",
        "role": "member",
        "last_login_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class IntegrityCommitSession(FakeSession):
    def __init__(self, *args, unique_error: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique_error = unique_error

    async def commit(self) -> None:
        orig: Any = UniqueViolationError("dup") if self.unique_error else Exception("boom")
        raise IntegrityError("stmt", {}, orig)

    async def rollback(self) -> None:
        return None


class DeleteResultSession(FakeSession):
    def __init__(self, *args, rowcount: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self._rowcount = rowcount

    async def execute(self, _stmt):
        return SimpleNamespace(rowcount=self._rowcount, all=lambda: [])

    async def rollback(self) -> None:
        return None


def test_list_users_returns_paginated(route_client) -> None:
    rows = [_user_row(email="a@x.com"), _user_row(email="b@x.com", role="admin")]
    session = FakeSession(scalars_values=[rows], scalar_values=[2])

    response = route_client(session=session).get("/v1/admin/users")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_list_users_requires_admin(route_client) -> None:
    response = route_client(user=user_principal(role="member")).get("/v1/admin/users")

    assert response.status_code == 403


def test_create_user_returns_409_when_duplicate(route_client, monkeypatch) -> None:
    from bigrag.routers import admin_users

    monkeypatch.setattr(admin_users, "hash_password", lambda _pw: "hashed")
    monkeypatch.setattr(admin_users.audit, "record", lambda *a, **k: None)

    session = IntegrityCommitSession(unique_error=True)
    client = route_client(session=session)

    response = client.post(
        "/v1/admin/users",
        json={
            "email": "dup@example.com",
            "password": "longenough",
            "display_name": "X",
            "role": "member",
        },
    )

    assert response.status_code == 409


def test_update_user_invalid_uuid_returns_404(route_client) -> None:
    response = route_client().patch("/v1/admin/users/not-a-uuid", json={"display_name": "n"})

    assert response.status_code == 404


def test_update_user_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).patch(
        f"/v1/admin/users/{uuid.uuid4()}",
        json={"display_name": "n"},
    )

    assert response.status_code == 404


def test_update_user_happy_path_with_password(route_client, monkeypatch) -> None:
    from bigrag.routers import admin_users

    monkeypatch.setattr(admin_users, "hash_password", lambda _pw: "new-hash")
    monkeypatch.setattr(admin_users.audit, "record", lambda *a, **k: None)

    async def noop_invalidate():
        return None

    monkeypatch.setattr(admin_users, "invalidate_auth_principals", noop_invalidate)

    target = _user_row()
    session = FakeSession(get_values={target.id: target})
    response = route_client(session=session).patch(
        f"/v1/admin/users/{target.id}",
        json={
            "display_name": "New",
            "role": "admin",
            "password": "longenough",
        },
    )

    assert response.status_code == 200
    assert target.display_name == "New"
    assert target.role == "admin"
    assert target.password_hash == "new-hash"


def test_delete_user_invalid_uuid(route_client) -> None:
    response = route_client().delete("/v1/admin/users/not-uuid")

    assert response.status_code == 404


def test_delete_user_blocks_self(route_client) -> None:
    me = user_principal()
    response = route_client(user=me).delete(f"/v1/admin/users/{me['id']}")

    assert response.status_code == 400
    assert "your own account" in response.json()["detail"]


def test_delete_user_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).delete(
        f"/v1/admin/users/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_delete_user_blocks_last_admin(route_client, monkeypatch) -> None:
    from bigrag.routers import admin_users

    async def noop_invalidate():
        return None

    monkeypatch.setattr(admin_users, "invalidate_auth_principals", noop_invalidate)
    monkeypatch.setattr(admin_users.audit, "record", lambda *a, **k: None)

    target = _user_row(role="admin")
    session = DeleteResultSession(get_values={target.id: target}, rowcount=0)

    response = route_client(session=session).delete(f"/v1/admin/users/{target.id}")

    assert response.status_code == 400
    assert "last admin" in response.json()["detail"]


def test_delete_user_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import admin_users

    async def noop_invalidate():
        return None

    monkeypatch.setattr(admin_users, "invalidate_auth_principals", noop_invalidate)
    monkeypatch.setattr(admin_users.audit, "record", lambda *a, **k: None)

    target = _user_row()
    session = DeleteResultSession(get_values={target.id: target}, rowcount=1)

    response = route_client(session=session).delete(f"/v1/admin/users/{target.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "User deleted"
