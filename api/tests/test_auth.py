"""E2E tests for bigRAG auth middleware and /v1/auth router.

Validates session-cookie auth, API-key Bearer auth, and unauthenticated
requests are rejected.
"""

from __future__ import annotations

import pytest

from tests.conftest import TEST_API_KEY, TEST_SESSION_TOKEN


@pytest.mark.asyncio
async def test_missing_auth_returns_401(client, no_auth_headers):
    client.cookies.clear()
    resp = await client.get("/v1/collections", headers=no_auth_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_bearer_returns_401(client, bad_auth_headers):
    client.cookies.clear()
    resp = await client.get("/v1/collections", headers=bad_auth_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_auth_succeeds(client, auth_headers, mock_db):
    client.cookies.clear()
    mock_db.fetch.return_value = []

    async def fetchrow(query: str, *args):
        if "COUNT(*)" in query and "collections" in query:
            return {"cnt": 0}
        if "FROM api_keys" in query and "JOIN users" in query:
            return await type(mock_db.fetchrow).side_effect.__wrapped__(query, *args) \
                if hasattr(mock_db.fetchrow.side_effect, "__wrapped__") else None
        return None

    resp = await client.get("/v1/collections", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_session_cookie_auth_succeeds(client, mock_db):
    mock_db.fetch.return_value = []
    client.cookies.set("bigrag_session", TEST_SESSION_TOKEN)
    resp = await client.get("/v1/collections")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bearer_prefix_required_for_api_key(client):
    client.cookies.clear()
    headers = {"Authorization": TEST_API_KEY}
    resp = await client.get("/v1/collections", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_setup_status_endpoint(client, mock_db):
    mock_db.fetchrow.side_effect = None
    mock_db.fetchrow.return_value = {"cnt": 0}
    resp = await client.get("/v1/auth/setup-status")
    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": True}


@pytest.mark.asyncio
async def test_health_does_not_require_auth(client, no_auth_headers):
    client.cookies.clear()
    resp = await client.get("/health", headers=no_auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session_for_user(client, mock_db):
    from tests.conftest import TEST_USER_ID

    client.cookies.set("bigrag_session", TEST_SESSION_TOKEN)
    resp = await client.post("/v1/auth/logout-all")

    assert resp.status_code == 200
    assert resp.json()["message"] == "Signed out of all devices"

    # Confirm the user-scoped delete actually ran.
    import uuid as _uuid

    delete_calls = [
        c for c in mock_db.execute.await_args_list
        if c.args
        and "DELETE FROM sessions" in c.args[0]
        and "WHERE user_id" in c.args[0]
        and c.args[1] == _uuid.UUID(TEST_USER_ID)
    ]
    assert delete_calls, (
        "logout-all must issue DELETE FROM sessions WHERE user_id"
    )


@pytest.mark.asyncio
async def test_logout_all_requires_auth(client):
    client.cookies.clear()
    resp = await client.post("/v1/auth/logout-all")
    assert resp.status_code == 401
