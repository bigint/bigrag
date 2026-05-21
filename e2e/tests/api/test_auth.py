"""End-to-end tests for bigrag.routers.auth.

Endpoints covered:
- GET  /v1/auth/setup-status
- POST /v1/auth/setup        (already-completed -> 409)
- POST /v1/auth/login        (success, wrong password, unknown email, missing fields)
- POST /v1/auth/logout
- POST /v1/auth/logout-all
- GET  /v1/auth/me
- GET  /v1/auth/whoami       (session + api_key auth methods)
- POST /v1/auth/password

Login rate limit is 10/min per IP+email; tests are intentionally frugal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from tests._helpers import assert_envelope

API_BASE_HEADERS = {"Origin": "http://localhost:4000"}


async def _login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
        headers=API_BASE_HEADERS,
    )


async def test_setup_status_returns_no_setup_needed(
    admin_setup: dict[str, str],
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/auth/setup-status")
    body = assert_envelope(resp, 200)
    assert body["needs_setup"] is False


async def test_setup_when_already_completed_returns_409(
    admin_setup: dict[str, str],
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/auth/setup",
        json={
            "email": "another-admin@example.com",
            "password": "another-strong-password-123!",
            "display_name": "Other",
        },
        headers=API_BASE_HEADERS,
    )
    assert resp.status_code == 409, resp.text


async def test_login_success_sets_session_cookie(
    admin_setup: dict[str, str],
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await _login(unauth_client, admin_setup["email"], admin_setup["password"])
    body = assert_envelope(resp, 200)
    assert body["user"]["email"] == admin_setup["email"]
    assert body["user"]["role"] == "admin"
    assert unauth_client.cookies.get("bigrag_session"), "session cookie not set"


async def test_login_wrong_password_returns_401(
    admin_setup: dict[str, str],
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await _login(unauth_client, admin_setup["email"], "definitely-wrong-pass-9!")
    assert resp.status_code == 401, resp.text


async def test_login_unknown_email_returns_401(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await _login(unauth_client, "no-such-user@example.com", "anything-strong-9!")
    assert resp.status_code == 401, resp.text


async def test_login_missing_fields_returns_422(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/auth/login",
        json={"email": "x@example.com"},
        headers=API_BASE_HEADERS,
    )
    assert resp.status_code == 422, resp.text


async def test_logout_clears_session_and_second_call_unauth(
    admin_client: httpx.AsyncClient,
) -> None:
    me_before = await admin_client.get("/v1/auth/me")
    assert me_before.status_code == 200

    logout = await admin_client.post("/v1/auth/logout")
    assert logout.status_code == 200, logout.text

    me_after = await admin_client.get("/v1/auth/me")
    assert me_after.status_code == 401, me_after.text


async def test_logout_all_invalidates_other_sessions(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
    unauth_client: httpx.AsyncClient,
) -> None:
    second_login = await _login(unauth_client, admin_setup["email"], admin_setup["password"])
    assert second_login.status_code == 200, second_login.text
    other_me = await unauth_client.get("/v1/auth/me")
    assert other_me.status_code == 200

    resp = await admin_client.post("/v1/auth/logout-all")
    assert resp.status_code == 200, resp.text

    after = await unauth_client.get("/v1/auth/me")
    assert after.status_code == 401, after.text


async def test_me_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/auth/me")
    assert resp.status_code == 401, resp.text


async def test_me_returns_admin_profile(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/auth/me")
    body = assert_envelope(resp, 200)
    assert body["user"]["email"] == admin_setup["email"]
    assert body["user"]["role"] == "admin"


async def test_whoami_session_auth(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/auth/whoami")
    body = assert_envelope(resp, 200)
    assert body["auth_method"] == "session"
    assert body["user_email"] == admin_setup["email"]
    assert body.get("api_key_id") is None


async def test_whoami_api_key_auth(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/auth/whoami")
    body = assert_envelope(resp, 200)
    assert body["auth_method"] == "api_key"
    assert body.get("api_key_id")


async def test_change_password_round_trip(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
    unauth_client: httpx.AsyncClient,
) -> None:
    temp_password = "e2e-temp-password-456!"
    original = admin_setup["password"]

    resp = await admin_client.post(
        "/v1/auth/password",
        json={"current_password": original, "new_password": temp_password},
    )
    assert resp.status_code == 200, resp.text

    me_after = await admin_client.get("/v1/auth/me")
    assert me_after.status_code == 401, "old session should be invalidated"

    new_client = unauth_client
    new_client.cookies.clear()
    bad_login = await _login(new_client, admin_setup["email"], original)
    assert bad_login.status_code == 401, "old password should not work"

    good_login = await _login(new_client, admin_setup["email"], temp_password)
    assert good_login.status_code == 200, good_login.text

    restore = await new_client.post(
        "/v1/auth/password",
        json={"current_password": temp_password, "new_password": original},
        headers=API_BASE_HEADERS,
    )
    assert restore.status_code == 200, restore.text


async def test_change_password_wrong_current_returns_401(
    admin_setup: dict[str, str],
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/auth/password",
        json={
            "current_password": "obviously-not-the-password-1!",
            "new_password": "another-strong-password-9!",
        },
    )
    assert resp.status_code == 401, resp.text


async def test_logout_all_requires_session_not_api_key(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.post("/v1/auth/logout-all")
    assert resp.status_code == 403, resp.text
