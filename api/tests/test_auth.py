"""E2E tests for bigRAG auth middleware.

Validates Bearer token authentication, query-param token fallback,
and proper 401 responses for missing or invalid credentials.
"""

from __future__ import annotations

import pytest

from tests.conftest import TEST_API_SECRET


@pytest.mark.asyncio
async def test_missing_auth_returns_401(client, no_auth_headers):
    """Request with no Authorization header should be rejected."""
    resp = await client.get("/v1/collections", headers=no_auth_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client, bad_auth_headers):
    """Request with an incorrect Bearer token should be rejected."""
    resp = await client.get("/v1/collections", headers=bad_auth_headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_bearer_token(client, auth_headers, mock_db):
    """Request with the correct Bearer token should succeed."""
    mock_db.fetch.return_value = []
    resp = await client.get("/v1/collections", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_query_param_token(client, mock_db):
    """Token passed as a query parameter should be accepted."""
    mock_db.fetch.return_value = []
    resp = await client.get(f"/v1/collections?token={TEST_API_SECRET}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_bearer_prefix_required(client):
    """Authorization header without 'Bearer ' prefix should be rejected."""
    headers = {"Authorization": TEST_API_SECRET}
    resp = await client.get("/v1/collections", headers=headers)
    assert resp.status_code == 401
