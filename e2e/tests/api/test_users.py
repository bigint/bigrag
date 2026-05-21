"""End-to-end tests for bigrag.routers.admin_users.

Endpoints covered:
- GET    /v1/admin/users
- POST   /v1/admin/users
- PATCH  /v1/admin/users/{id}
- DELETE /v1/admin/users/{id}
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest
import pytest_asyncio

from tests._helpers import assert_envelope, unique_name

API_BASE_HEADERS = {"Origin": "http://localhost:4000"}
MEMBER_PASSWORD = "e2e-member-password-9!"


async def _make_email(prefix: str = "e2e-user") -> str:
    return f"{unique_name(prefix)}@example.com"


@pytest_asyncio.fixture
async def user_factory(
    admin_client: httpx.AsyncClient,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    """Create users via admin; delete them on teardown."""
    created_ids: list[str] = []

    async def _create(
        *,
        email: str | None = None,
        password: str = MEMBER_PASSWORD,
        role: str = "member",
        display_name: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "email": email or await _make_email(),
            "password": password,
            "role": role,
            "display_name": display_name or unique_name("name"),
        }
        resp = await admin_client.post("/v1/admin/users", json=payload)
        body = assert_envelope(resp, 201)
        created_ids.append(body["id"])
        return body

    yield _create

    for uid in created_ids:
        try:
            await admin_client.delete(f"/v1/admin/users/{uid}")
        except Exception:
            pass


async def test_list_users_returns_admin(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/users", params={"include_total": "true"})
    body = assert_envelope(resp, 200)
    assert body["total"] >= 1
    emails = {u["email"] for u in body["users"]}
    assert admin_setup["email"] in emails


async def test_list_users_pagination(
    admin_client: httpx.AsyncClient,
    user_factory: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    await user_factory()
    await user_factory()
    resp = await admin_client.get(
        "/v1/admin/users", params={"limit": 1, "offset": 0, "include_total": "true"}
    )
    body = assert_envelope(resp, 200)
    assert len(body["users"]) == 1
    assert body["total"] >= 3


async def test_create_member_and_admin_users(
    user_factory: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    member = await user_factory(role="member")
    admin = await user_factory(role="admin")
    assert member["role"] == "member"
    assert admin["role"] == "admin"
    assert "password" not in member
    assert "password_hash" not in member


async def test_create_user_duplicate_email_returns_409(
    admin_client: httpx.AsyncClient,
    user_factory: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    existing = await user_factory()
    resp = await admin_client.post(
        "/v1/admin/users",
        json={
            "email": existing["email"],
            "password": MEMBER_PASSWORD,
            "role": "member",
            "display_name": "Dup",
        },
    )
    assert resp.status_code == 409, resp.text


async def test_create_user_missing_password_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    email = await _make_email("nopw")
    resp = await admin_client.post(
        "/v1/admin/users",
        json={"email": email, "role": "member", "display_name": "X"},
    )
    assert resp.status_code == 422, resp.text


async def test_patch_user_rename_and_role_change(
    admin_client: httpx.AsyncClient,
    user_factory: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    user = await user_factory(role="member")
    new_name = unique_name("renamed")
    resp = await admin_client.patch(
        f"/v1/admin/users/{user['id']}",
        json={"display_name": new_name, "role": "admin"},
    )
    body = assert_envelope(resp, 200)
    assert body["display_name"] == new_name
    assert body["role"] == "admin"


async def test_patch_user_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.patch(
        "/v1/admin/users/00000000-0000-0000-0000-000000000000",
        json={"display_name": "x"},
    )
    assert resp.status_code == 404, resp.text


async def test_delete_user_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.delete("/v1/admin/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text


async def test_cannot_delete_self(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    me = await admin_client.get("/v1/auth/me")
    my_id = me.json()["user"]["id"]
    resp = await admin_client.delete(f"/v1/admin/users/{my_id}")
    assert resp.status_code == 400, resp.text


async def test_cannot_demote_last_admin(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    users = await admin_client.get("/v1/admin/users")
    admins = [u for u in users.json()["users"] if u["role"] == "admin"]
    if len(admins) != 1:
        pytest.skip("multiple admins present; cannot exercise last-admin guard safely")
    only_admin = admins[0]
    resp = await admin_client.patch(
        f"/v1/admin/users/{only_admin['id']}",
        json={"role": "member"},
    )
    assert resp.status_code == 400, resp.text


async def test_cannot_delete_last_admin(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    users = await admin_client.get("/v1/admin/users")
    admins = [u for u in users.json()["users"] if u["role"] == "admin"]
    me = (await admin_client.get("/v1/auth/me")).json()["user"]
    others = [a for a in admins if a["id"] != me["id"]]
    if others:
        pytest.skip("another admin exists; last-admin delete guard not exercisable")
    resp = await admin_client.delete(f"/v1/admin/users/{me['id']}")
    assert resp.status_code == 400, resp.text


async def test_non_admin_user_blocked_on_admin_endpoints(
    user_factory: Callable[..., Awaitable[dict[str, Any]]],
    unauth_client: httpx.AsyncClient,
) -> None:
    member = await user_factory(role="member")
    login = await unauth_client.post(
        "/v1/auth/login",
        json={"email": member["email"], "password": MEMBER_PASSWORD},
        headers=API_BASE_HEADERS,
    )
    assert login.status_code == 200, login.text

    list_resp = await unauth_client.get("/v1/admin/users")
    assert list_resp.status_code == 403, list_resp.text

    create_resp = await unauth_client.post(
        "/v1/admin/users",
        json={
            "email": await _make_email("blocked"),
            "password": MEMBER_PASSWORD,
            "role": "member",
            "display_name": "x",
        },
        headers=API_BASE_HEADERS,
    )
    assert create_resp.status_code == 403, create_resp.text

    patch_resp = await unauth_client.patch(
        f"/v1/admin/users/{member['id']}",
        json={"display_name": "nope"},
        headers=API_BASE_HEADERS,
    )
    assert patch_resp.status_code == 403, patch_resp.text

    delete_resp = await unauth_client.delete(
        f"/v1/admin/users/{member['id']}",
        headers=API_BASE_HEADERS,
    )
    assert delete_resp.status_code == 403, delete_resp.text
