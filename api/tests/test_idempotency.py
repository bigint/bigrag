"""Tests for the Idempotency-Key middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import install_fetchrow_router, make_collection_row


@pytest.fixture
def mock_redis_cache():
    """Patch redis_cache get/set to an in-memory dict."""
    store: dict[str, dict] = {}

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, value, ttl):
        store[key] = value

    with patch("bigrag.middleware.idempotency.redis_cache.get", side_effect=fake_get), patch(
        "bigrag.middleware.idempotency.redis_cache.set", side_effect=fake_set
    ):
        yield store


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_idempotency_header_replays_cached_response(
    _mock_emb, client, mock_db, auth_headers, mock_redis_cache
):
    """Two POSTs with the same Idempotency-Key must return the same
    response, with the second call not re-inserting into the DB."""
    row = make_collection_row("idem_col")

    def router(query, *args):
        if "SELECT id FROM collections WHERE name" in query:
            return None
        if "INSERT INTO collections" in query:
            return row
        return None

    install_fetchrow_router(mock_db, router)

    headers = {**auth_headers, "Idempotency-Key": "my-key-abc123"}
    body = {"name": "idem_col", "embedding_api_key": "sk-test"}

    resp1 = await client.post("/v1/collections", json=body, headers=headers)
    assert resp1.status_code == 201, resp1.text
    first_body = resp1.json()

    # Simulate a second call — the handler would also succeed, but the
    # middleware should replay the cached response instead.
    # To prove the handler wasn't called again, swap the router to
    # return a different row. If the middleware replayed correctly, the
    # response body will match resp1 and NOT reflect the swap.
    different = make_collection_row("idem_col", description="would-differ")
    install_fetchrow_router(
        mock_db,
        lambda q, *a: different if "INSERT INTO collections" in q else None,
    )

    resp2 = await client.post("/v1/collections", json=body, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json() == first_body
    assert resp2.headers.get("idempotency-key-replayed") == "true"


@patch("bigrag.services.embedding.get_embedding_model", return_value=MagicMock())
async def test_different_idempotency_keys_do_not_collide(
    _mock_emb, client, mock_db, auth_headers, mock_redis_cache
):
    row = make_collection_row("col_1")

    def router(query, *args):
        if "SELECT id FROM collections WHERE name" in query:
            return None
        if "INSERT INTO collections" in query:
            return row
        return None

    install_fetchrow_router(mock_db, router)

    r1 = await client.post(
        "/v1/collections",
        json={"name": "col_1", "embedding_api_key": "sk-test"},
        headers={**auth_headers, "Idempotency-Key": "key-a"},
    )
    r2 = await client.post(
        "/v1/collections",
        json={"name": "col_1", "embedding_api_key": "sk-test"},
        headers={**auth_headers, "Idempotency-Key": "key-b"},
    )
    # Second call is a fresh attempt (different key). Router now returns
    # 409 semantics on real infra, but our mock returns the row again so
    # both succeed — what matters is there's no replay header on r2.
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r2.headers.get("idempotency-key-replayed") is None


async def test_get_requests_ignore_idempotency_header(
    client, mock_db, auth_headers, mock_redis_cache
):
    # GET is idempotent by definition — middleware must not touch it.
    resp = await client.get(
        "/v1/collections",
        headers={**auth_headers, "Idempotency-Key": "whatever"},
    )
    # Response code not important here; what matters is no cache interaction
    # and no replay header.
    assert resp.headers.get("idempotency-key-replayed") is None
    assert not mock_redis_cache  # nothing got written
