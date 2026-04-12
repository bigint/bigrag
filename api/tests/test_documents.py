"""E2E tests for bigRAG document endpoints.

Covers upload, list, get, delete, reprocess, chunks, and file download
under /v1/collections/{name}/documents.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import _install_auth_fetchrow, make_collection_row, make_document_row


def _setup_fetchrow(mock_db, col_row, doc_row):
    """Wire mock_db.fetchrow to route queries to the right row.

    Reassigning ``mock_db.fetchrow`` drops the auth wrapper installed by
    ``_install_auth_fetchrow``, so we re-install it after swapping.
    """

    async def fetchrow_router(query, *args):
        if "collections WHERE name" in query:
            return col_row
        if "documents WHERE id" in query:
            return doc_row
        if "INSERT INTO documents" in query:
            return doc_row
        if "COUNT(*)" in query:
            return {"cnt": 1}
        return None

    mock_db.fetchrow = AsyncMock(side_effect=fetchrow_router)
    _install_auth_fetchrow(mock_db)




@pytest.mark.asyncio
async def test_upload_document(client, auth_headers, mock_db, mock_storage):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)

    with patch(
        "bigrag.routers.documents.get_embedding_model_for",
        return_value=MagicMock(),
    ):
        resp = await client.post(
            "/v1/collections/test_col/documents",
            headers=auth_headers,
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            data={"metadata": "{}"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "test.pdf"
    assert body["status"] == "ready"


@pytest.mark.asyncio
async def test_upload_marks_failed_when_enqueue_errors(
    client, auth_headers, mock_db, mock_storage, mock_queue
):
    """If Redis enqueue fails after DB insert, the document must be
    marked status=failed and the endpoint must return 503 (not leave a
    zombie pending row)."""
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)
    mock_queue.enqueue = AsyncMock(side_effect=RuntimeError("redis unreachable"))

    with patch(
        "bigrag.routers.documents.get_embedding_model_for",
        return_value=MagicMock(),
    ):
        resp = await client.post(
            "/v1/collections/test_col/documents",
            headers=auth_headers,
            files={"file": ("zombie.pdf", b"fake pdf", "application/pdf")},
            data={"metadata": "{}"},
        )

    assert resp.status_code == 503, resp.text
    # The router must have issued an UPDATE to mark the doc failed.
    update_calls = [
        call for call in mock_db.execute.await_args_list
        if call.args and "UPDATE documents" in call.args[0]
           and "status = 'failed'" in call.args[0]
    ]
    assert update_calls, (
        f"Expected UPDATE documents SET status='failed' after enqueue failure. "
        f"Got execute calls: {[c.args[:1] for c in mock_db.execute.await_args_list]}"
    )


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client, auth_headers, mock_db):
    col_row = make_collection_row("test_col")
    _setup_fetchrow(mock_db, col_row, None)

    with patch(
        "bigrag.routers.documents.get_embedding_model_for",
        return_value=MagicMock(),
    ):
        resp = await client.post(
            "/v1/collections/test_col/documents",
            headers=auth_headers,
            files={"file": ("malware.exe", b"bad content", "application/octet-stream")},
            data={"metadata": "{}"},
        )

    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]




@pytest.mark.asyncio
async def test_list_documents(client, auth_headers, mock_db):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)
    mock_db.fetch = AsyncMock(return_value=[doc_row])

    resp = await client.get(
        "/v1/collections/test_col/documents",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["documents"]) == 1
    assert body["documents"][0]["filename"] == "test.pdf"




@pytest.mark.asyncio
async def test_get_document(client, auth_headers, mock_db):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)

    doc_id = str(doc_row["id"])
    resp = await client.get(
        f"/v1/collections/test_col/documents/{doc_id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_get_document_not_found(client, auth_headers, mock_db):
    col_row = make_collection_row("test_col")
    _setup_fetchrow(mock_db, col_row, None)

    resp = await client.get(
        "/v1/collections/test_col/documents/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()




@pytest.mark.asyncio
async def test_delete_document(client, auth_headers, mock_db, mock_vector_store, mock_storage):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)

    with patch("bigrag.routers.documents.vector_store", mock_vector_store):
        doc_id = str(doc_row["id"])
        resp = await client.delete(
            f"/v1/collections/test_col/documents/{doc_id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"




@pytest.mark.asyncio
async def test_reprocess_document(client, auth_headers, mock_db, mock_vector_store, mock_storage):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)
    mock_storage.exists = AsyncMock(return_value=True)

    with (
        patch(
            "bigrag.routers.documents.get_embedding_model_for",
            return_value=MagicMock(),
        ),
        patch("bigrag.routers.documents.vector_store", mock_vector_store),
    ):
        doc_id = str(doc_row["id"])
        resp = await client.post(
            f"/v1/collections/test_col/documents/{doc_id}/reprocess",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"




@pytest.mark.asyncio
async def test_get_document_chunks(client, auth_headers, mock_db, mock_vector_store):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)

    sample_chunks = [
        {"id": "chunk-1", "text": "Hello world", "metadata": {}},
        {"id": "chunk-2", "text": "Foo bar", "metadata": {}},
    ]
    mock_vector_store.get_chunks = AsyncMock(return_value=(sample_chunks, 2))

    with patch("bigrag.routers.documents.vector_store", mock_vector_store):
        doc_id = str(doc_row["id"])
        resp = await client.get(
            f"/v1/collections/test_col/documents/{doc_id}/chunks",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["chunks"]) == 2




@pytest.mark.asyncio
async def test_download_document_file(client, auth_headers, mock_db, mock_storage):
    col_row = make_collection_row("test_col")
    doc_row = make_document_row(collection_id=str(col_row["id"]))
    _setup_fetchrow(mock_db, col_row, doc_row)

    file_bytes = b"binary pdf content here"
    mock_storage.exists = AsyncMock(return_value=True)
    mock_storage.get = AsyncMock(return_value=file_bytes)

    doc_id = str(doc_row["id"])
    resp = await client.get(
        f"/v1/collections/test_col/documents/{doc_id}/file",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.content == file_bytes
    assert "application/pdf" in resp.headers["content-type"]
