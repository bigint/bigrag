"""E2E tests for collection CRUD endpoints (POST/GET/PUT/DELETE /v1/collections)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_collection_row


# ---------------------------------------------------------------------------
# POST /v1/collections
# ---------------------------------------------------------------------------


@patch(
    "bigrag.services.embedding.get_embedding_model",
    return_value=MagicMock(),
)
async def test_create_collection(_mock_emb, client, mock_db, auth_headers):
    row = make_collection_row("test_col")

    # First fetchrow: duplicate check → None (no conflict)
    # Second fetchrow: INSERT RETURNING * → the new row
    mock_db.fetchrow.side_effect = [None, row]

    resp = await client.post(
        "/v1/collections",
        json={"name": "test_col", "embedding_api_key": "sk-test"},
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_col"
    assert data["embedding_provider"] == "openai"
    assert data["embedding_model"] == "text-embedding-3-small"
    assert data["dimension"] == 1536


@patch(
    "bigrag.services.embedding.get_embedding_model",
    return_value=MagicMock(),
)
async def test_create_duplicate_collection_returns_409(
    _mock_emb, client, mock_db, auth_headers
):
    existing = make_collection_row("test_col")

    # The duplicate-check fetchrow returns a row → 409
    mock_db.fetchrow.return_value = existing

    resp = await client.post(
        "/v1/collections",
        json={"name": "test_col"},
        headers=auth_headers,
    )

    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


async def test_create_collection_invalid_name_returns_422(client, mock_db, auth_headers):
    resp = await client.post(
        "/v1/collections",
        json={"name": "bad name!"},
        headers=auth_headers,
    )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/collections
# ---------------------------------------------------------------------------


async def test_list_collections(client, mock_db, auth_headers):
    rows = [make_collection_row("col_a"), make_collection_row("col_b")]
    mock_db.fetch.return_value = rows

    resp = await client.get("/v1/collections", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["collections"]) == 2
    names = {c["name"] for c in data["collections"]}
    assert names == {"col_a", "col_b"}


async def test_list_collections_empty(client, mock_db, auth_headers):
    mock_db.fetch.return_value = []

    resp = await client.get("/v1/collections", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["collections"] == []


# ---------------------------------------------------------------------------
# GET /v1/collections/{name}
# ---------------------------------------------------------------------------


async def test_get_collection(client, mock_db, auth_headers):
    row = make_collection_row("my_col")
    mock_db.fetchrow.return_value = row

    resp = await client.get("/v1/collections/my_col", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "my_col"
    assert data["dimension"] == 1536
    assert "has_api_key" in data


async def test_get_collection_not_found(client, mock_db, auth_headers):
    mock_db.fetchrow.return_value = None

    resp = await client.get("/v1/collections/nonexistent", headers=auth_headers)

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PUT /v1/collections/{name}
# ---------------------------------------------------------------------------


async def test_update_collection(client, mock_db, auth_headers):
    original = make_collection_row("upd_col")
    updated = make_collection_row("upd_col", description="new desc")

    # First fetchrow: find existing row
    # Second fetchrow: UPDATE RETURNING *
    mock_db.fetchrow.side_effect = [original, updated]

    resp = await client.put(
        "/v1/collections/upd_col",
        json={"description": "new desc"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "upd_col"
    assert data["description"] == "new desc"


# ---------------------------------------------------------------------------
# DELETE /v1/collections/{name}
# ---------------------------------------------------------------------------


async def test_delete_collection(client, mock_db, mock_vector_store, auth_headers):
    row = make_collection_row("del_col")
    mock_db.fetchrow.return_value = row

    resp = await client.delete("/v1/collections/del_col", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    mock_vector_store.delete_collection.assert_called_once_with("del_col")


async def test_delete_collection_not_found(client, mock_db, auth_headers):
    mock_db.fetchrow.return_value = None

    resp = await client.delete("/v1/collections/ghost", headers=auth_headers)

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
