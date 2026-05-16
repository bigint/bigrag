"""SDK contract tests for ``bigrag.AuthResource``.

Touches every public method on the resource::

    setup_status, setup, login, logout, logout_all, me, whoami,
    change_password, get_preferences, update_preferences

The ``setup`` endpoint is exercised only via its 409-when-already-done
behaviour: the e2e instance is bootstrapped with an admin before the
test session starts, so a fresh setup call cannot succeed without
destroying global fixtures.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from bigrag import APIError, AuthenticationError, BigRAG, NotFoundError
from tests._helpers import unique_name


async def test_setup_status_returns_typed_response(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    status = await client.auth.setup_status()
    assert "needs_setup" in status
    assert isinstance(status["needs_setup"], bool)
    assert status["needs_setup"] is False


async def test_setup_when_already_done_raises(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    """Already-completed setup returns 409, surfaced as ``APIError``."""
    client = await sdk_client()
    with pytest.raises(APIError) as excinfo:
        await client.auth.setup(
            {
                "email": "should-not-exist@example.com",
                "password": "irrelevant-pass-9!",
                "display_name": "nope",
            }
        )
    assert excinfo.value.status == 409


async def test_whoami_api_key_principal(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    api_key: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    minted = await api_key(name=unique_name("sdk-auth"), scopes=["collection:read"])
    client = await sdk_client(key=minted)
    whoami = await client.auth.whoami()
    assert whoami["authenticated"] is True
    assert whoami["auth_method"] == "api_key"
    assert whoami["api_key_id"] == minted["id"]
    assert whoami["api_key_name"] == minted["name"]
    assert whoami["scopes"] == ["collection:read"]


async def test_session_whoami_and_me(
    session_sdk_client: BigRAG,
    admin_setup: dict[str, str],
) -> None:
    whoami = await session_sdk_client.auth.whoami()
    assert whoami["authenticated"] is True
    assert whoami["auth_method"] == "session"
    assert whoami["user_email"] == admin_setup["email"]

    me = await session_sdk_client.auth.me()
    assert me["user"]["email"] == admin_setup["email"]
    assert me["user"]["role"] == "admin"


async def test_session_login_via_sdk_starts_session(
    api_base_url: str,
    admin_setup: dict[str, str],
) -> None:
    """``BigRAG(http_client=...).auth.login`` populates the cookie jar."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={"Origin": api_base_url},
    ) as http:
        client = BigRAG(api_key="", base_url=api_base_url, http_client=http)
        session = await client.auth.login(
            {"email": admin_setup["email"], "password": admin_setup["password"]}
        )
        assert session["user"]["email"] == admin_setup["email"]
        assert http.cookies.get("bigrag_session"), "session cookie not set"
        # logout cleans up the cookie
        await client.auth.logout()


async def test_session_logout_all_revokes_session(
    api_base_url: str,
    admin_setup: dict[str, str],
) -> None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={"Origin": api_base_url},
    ) as http:
        client = BigRAG(api_key="", base_url=api_base_url, http_client=http)
        await client.auth.login(
            {"email": admin_setup["email"], "password": admin_setup["password"]}
        )
        resp = await client.auth.logout_all()
        assert resp["status"] == "ok"
        # subsequent session call must now 401
        with pytest.raises(AuthenticationError):
            await client.auth.me()


async def test_preferences_round_trip_via_sdk(
    admin_client: httpx.AsyncClient,
    api_base_url: str,
) -> None:
    """Create a fresh member, log in via the SDK, round-trip preferences."""
    email = f"{unique_name('sdk-pref')}@example.com"
    password = "sdk-member-pass-9!"
    create_resp = await admin_client.post(
        "/v1/admin/users",
        json={
            "email": email,
            "password": password,
            "role": "member",
            "display_name": unique_name("sdk"),
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    user_id = create_resp.json()["id"]

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"Origin": api_base_url},
        ) as http:
            client = BigRAG(api_key="", base_url=api_base_url, http_client=http)
            await client.auth.login({"email": email, "password": password})
            marker = unique_name("pref")
            updated = await client.auth.update_preferences({"sidebar": marker})
            assert updated["data"]["sidebar"] == marker
            roundtrip = await client.auth.get_preferences()
            assert roundtrip["data"]["sidebar"] == marker
    finally:
        await admin_client.delete(f"/v1/admin/users/{user_id}")


async def test_change_password_via_sdk(
    admin_client: httpx.AsyncClient,
    api_base_url: str,
) -> None:
    email = f"{unique_name('sdk-pwd')}@example.com"
    original = "sdk-pwd-original-9!"
    rotated = "sdk-pwd-rotated-9!"
    create_resp = await admin_client.post(
        "/v1/admin/users",
        json={
            "email": email,
            "password": original,
            "role": "member",
            "display_name": unique_name("pwd"),
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    user_id = create_resp.json()["id"]

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"Origin": api_base_url},
        ) as http:
            client = BigRAG(api_key="", base_url=api_base_url, http_client=http)
            await client.auth.login({"email": email, "password": original})
            resp = await client.auth.change_password(
                {"current_password": original, "new_password": rotated}
            )
            assert resp["status"] == "ok"
    finally:
        await admin_client.delete(f"/v1/admin/users/{user_id}")


async def test_api_key_whoami_with_collection_pin(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    api_key: Callable[..., Awaitable[dict[str, Any]]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    minted = await api_key(name=unique_name("pin"), collection=pinned["name"])
    client = await sdk_client(key=minted)
    whoami = await client.auth.whoami()
    assert whoami["collection"] == pinned["name"]


async def test_session_logout_then_whoami_unauthenticated(
    api_base_url: str,
    admin_setup: dict[str, str],
) -> None:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={"Origin": api_base_url},
    ) as http:
        client = BigRAG(api_key="", base_url=api_base_url, http_client=http)
        await client.auth.login(
            {"email": admin_setup["email"], "password": admin_setup["password"]}
        )
        await client.auth.logout()
        with pytest.raises((AuthenticationError, NotFoundError)):
            await client.auth.me()
