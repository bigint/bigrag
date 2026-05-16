"""End-to-end tests for bigrag.routers.preferences.

Endpoints covered:
- GET /v1/auth/preferences
- PUT /v1/auth/preferences

PUT semantics (per router source):
- Body may be ``{"data": {...}}`` or a bare ``{...}``; data deep-merges
  into the existing record.
- Sensitive paths (currently ``chat.openai_key``) are validated against
  the OpenAI API at write time. Round-trip tests avoid those paths so
  they don't reach the network during e2e.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio

from tests._helpers import assert_envelope, unique_name

API_BASE_HEADERS = {"Origin": "http://localhost:4000"}
MEMBER_PASSWORD = "e2e-member-password-9!"


@pytest_asyncio.fixture
async def temp_member_client(
    admin_client: httpx.AsyncClient,
    unauth_client: httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    """Create a member, return a logged-in client. Delete the member on teardown."""
    email = f"{unique_name('e2e-pref')}@example.com"
    resp = await admin_client.post(
        "/v1/admin/users",
        json={
            "email": email,
            "password": MEMBER_PASSWORD,
            "role": "member",
            "display_name": unique_name("pref"),
        },
    )
    body = assert_envelope(resp, 201)
    user_id = body["id"]

    member_client = httpx.AsyncClient(
        base_url=str(unauth_client.base_url),
        timeout=30.0,
        follow_redirects=True,
    )
    login = await member_client.post(
        "/v1/auth/login",
        json={"email": email, "password": MEMBER_PASSWORD},
        headers=API_BASE_HEADERS,
    )
    assert login.status_code == 200, login.text

    try:
        yield member_client
    finally:
        await member_client.aclose()
        try:
            await admin_client.delete(f"/v1/admin/users/{user_id}")
        except Exception:
            pass


async def test_get_preferences_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/auth/preferences")
    assert resp.status_code == 401, resp.text


async def test_put_preferences_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.put(
        "/v1/auth/preferences",
        json={"data": {"theme": "dark"}},
        headers=API_BASE_HEADERS,
    )
    assert resp.status_code == 401, resp.text


async def test_preferences_round_trip(temp_member_client: httpx.AsyncClient) -> None:
    marker = unique_name("val")
    put_resp = await temp_member_client.put(
        "/v1/auth/preferences",
        json={"data": {"theme": "dark", "ui": {"sidebar": marker}}},
        headers=API_BASE_HEADERS,
    )
    body = assert_envelope(put_resp, 200)
    assert body["data"]["theme"] == "dark"
    assert body["data"]["ui"]["sidebar"] == marker

    get_resp = await temp_member_client.get("/v1/auth/preferences")
    body = assert_envelope(get_resp, 200)
    assert body["data"]["theme"] == "dark"
    assert body["data"]["ui"]["sidebar"] == marker


async def test_preferences_deep_merge_preserves_other_keys(
    temp_member_client: httpx.AsyncClient,
) -> None:
    await temp_member_client.put(
        "/v1/auth/preferences",
        json={"data": {"theme": "dark", "ui": {"sidebar": "left", "density": "cozy"}}},
        headers=API_BASE_HEADERS,
    )
    put_resp = await temp_member_client.put(
        "/v1/auth/preferences",
        json={"data": {"ui": {"sidebar": "right"}}},
        headers=API_BASE_HEADERS,
    )
    body = assert_envelope(put_resp, 200)
    assert body["data"]["theme"] == "dark", "top-level key should be preserved"
    assert body["data"]["ui"]["sidebar"] == "right", "nested override should win"
    assert body["data"]["ui"]["density"] == "cozy", "untouched nested key preserved"


async def test_preferences_bare_dict_body_accepted(
    temp_member_client: httpx.AsyncClient,
) -> None:
    put_resp = await temp_member_client.put(
        "/v1/auth/preferences",
        json={"theme": "light"},
        headers=API_BASE_HEADERS,
    )
    body = assert_envelope(put_resp, 200)
    assert body["data"]["theme"] == "light"


async def test_preferences_separate_users_separate_scopes(
    admin_client: httpx.AsyncClient,
    temp_member_client: httpx.AsyncClient,
) -> None:
    member_marker = unique_name("member")
    admin_marker = unique_name("admin")

    await temp_member_client.put(
        "/v1/auth/preferences",
        json={"data": {"who": member_marker}},
        headers=API_BASE_HEADERS,
    )
    await admin_client.put(
        "/v1/auth/preferences",
        json={"data": {"who": admin_marker}},
    )

    member_get = await temp_member_client.get("/v1/auth/preferences")
    admin_get = await admin_client.get("/v1/auth/preferences")
    assert member_get.json()["data"]["who"] == member_marker
    assert admin_get.json()["data"]["who"] == admin_marker
