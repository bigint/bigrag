"""Tests for scoped API keys and the audit log."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from bigrag.services.scopes import has_scope, required_scope, scope_matches
from tests.conftest import install_fetchrow_router


class TestScopeMatching:
    def test_wildcard_resource(self):
        assert scope_matches("*:read", "collection:read") is True
        assert scope_matches("*:read", "document:read") is True
        assert scope_matches("*:read", "document:write") is False

    def test_wildcard_action(self):
        assert scope_matches("collection:*", "collection:read") is True
        assert scope_matches("collection:*", "collection:write") is True
        assert scope_matches("collection:*", "document:read") is False

    def test_full_wildcard(self):
        assert scope_matches("*:*", "anything:here") is True

    def test_exact_match(self):
        assert scope_matches("query:read", "query:read") is True
        assert scope_matches("query:read", "query:write") is False

    def test_empty_scope_is_falsy(self):
        assert scope_matches("", "query:read") is False

    def test_has_scope_empty_list_is_full_access(self):
        # Legacy keys with no scopes should NOT be denied.
        assert has_scope(None, "collection:read") is True
        assert has_scope([], "collection:read") is True

    def test_has_scope_with_restricted_set(self):
        scopes = ["collection:read", "query:read"]
        assert has_scope(scopes, "collection:read") is True
        assert has_scope(scopes, "collection:write") is False
        assert has_scope(scopes, "document:upload") is False


class TestEndpointScopeMap:
    def test_get_collections_needs_collection_read(self):
        assert required_scope("GET", "/v1/collections") == "collection:read"

    def test_post_query_needs_query_read(self):
        assert required_scope("POST", "/v1/collections/abc/query") == "query:read"

    def test_upload_needs_document_upload(self):
        assert (
            required_scope("POST", "/v1/collections/abc/documents") == "document:upload"
        )

    def test_health_is_unscoped(self):
        assert required_scope("GET", "/health") is None


@pytest.mark.asyncio
async def test_scoped_key_denied_on_mismatched_action(
    client, auth_headers, mock_db
):
    """An API key with only collection:read should 403 on upload."""
    from datetime import UTC, datetime

    from bigrag.services.auth import hash_api_key, hash_session_token
    from tests.conftest import (
        TEST_API_KEY,
        TEST_API_KEY_ID,
        TEST_SESSION_TOKEN,
        TEST_USER_ID,
        make_user_row,
    )

    # Rebuild the auth wrapper to declare scopes=[collection:read].
    user = make_user_row(user_id=TEST_USER_ID)
    session_row = dict(user)
    api_key_row = dict(user)
    api_key_row["api_key_id"] = uuid.UUID(TEST_API_KEY_ID)
    api_key_row["api_key_permissions"] = {"scopes": ["collection:read"]}
    api_key_row["api_key_rate_limits"] = {}

    async def fetchrow(query, *args):
        if "FROM sessions" in query:
            return session_row if args and args[0] == hash_session_token(
                TEST_SESSION_TOKEN
            ) else None
        if "FROM api_keys" in query and "JOIN users" in query:
            return api_key_row if args and args[0] == hash_api_key(TEST_API_KEY) else None
        return None

    mock_db.fetchrow = AsyncMock(side_effect=fetchrow)
    client.cookies.clear()  # force bearer path
    resp = await client.post(
        "/v1/collections/any/documents",
        headers=auth_headers,
        files={"file": ("x.pdf", b"%PDF-1.4\nx", "application/pdf")},
    )
    assert resp.status_code == 403
    assert "missing required scope" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_audit_list_endpoint_returns_entries(client, auth_headers, mock_db):
    from datetime import UTC, datetime

    entry_rows = [
        {
            "id": uuid.uuid4(),
            "actor_id": uuid.uuid4(),
            "actor_email": "a@example.com",
            "api_key_id": None,
            "action": "collection.create",
            "resource_type": "collection",
            "resource_id": "docs",
            "metadata": {"name": "docs"},
            "ip": "127.0.0.1",
            "user_agent": "pytest",
            "created_at": datetime.now(UTC),
        },
    ]

    async def fetch(sql, *args):
        if "FROM audit_log" in sql:
            return entry_rows
        return []

    mock_db.fetch = AsyncMock(side_effect=fetch)
    install_fetchrow_router(
        mock_db,
        lambda q, *a: {"cnt": len(entry_rows)} if "COUNT(*) AS cnt FROM audit_log" in q else None,
    )

    resp = await client.get("/v1/admin/audit", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["entries"][0]["action"] == "collection.create"
