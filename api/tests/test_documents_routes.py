from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession


def _document_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "collection_id": uuid.uuid4(),
        "filename": "f.txt",
        "file_type": "txt",
        "file_size": 12,
        "file_path": "docs/f.txt",
        "chunk_count": 3,
        "token_count": 100,
        "content_hash": "abc123",
        "status": "ready",
        "error_message": None,
        "meta": {},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def patch_documents_helpers(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import documents

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    def fake_embedding(_collection):
        return object()

    async def fake_get_values(keys):
        return {key: 100 for key in keys}

    async def noop(*_args, **_kwargs):
        return None

    async def fake_latest(_doc_id):
        return None

    async def fake_latest_many(_doc_ids):
        return {}

    monkeypatch.setattr(documents, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(documents, "get_embedding_model_for", fake_embedding)
    monkeypatch.setattr(documents, "get_values", fake_get_values)
    monkeypatch.setattr(documents.event_bus, "latest", fake_latest)
    monkeypatch.setattr(documents.event_bus, "latest_many", fake_latest_many)
    monkeypatch.setattr(documents.audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(documents.collection_cache, "invalidate", noop)
    monkeypatch.setattr(documents, "invalidate_collection_query_cache", noop)
    return monkeypatch


def test_upload_document_collection_not_found(route_client, monkeypatch) -> None:
    from fastapi import HTTPException

    from bigrag.routers import documents

    async def missing(_name):
        raise HTTPException(status_code=404, detail="Collection not found")

    monkeypatch.setattr(documents, "get_collection_or_404", missing)

    response = route_client().post(
        "/v1/collections/missing/documents",
        files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 404


def test_upload_document_embedding_error(route_client, monkeypatch) -> None:
    from bigrag.routers import documents

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name}

    def fail_embedding(_collection):
        raise ValueError("bad model")

    monkeypatch.setattr(documents, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(documents, "get_embedding_model_for", fail_embedding)

    response = route_client().post(
        "/v1/collections/docs/documents",
        files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400


def test_upload_document_unsupported_extension(route_client, patch_documents_helpers) -> None:
    response = route_client().post(
        "/v1/collections/docs/documents",
        files={"file": ("x.exe", io.BytesIO(b"hello"), "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_document_too_large_by_content_length(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    async def small_limits(_keys):
        return {"max_upload_size_mb": 1}

    monkeypatch.setattr(documents, "get_values", small_limits)

    big = b"x" * (2 * 1024 * 1024)
    response = route_client().post(
        "/v1/collections/docs/documents",
        files={"file": ("x.txt", io.BytesIO(big), "text/plain")},
        headers={"Content-Length": str(len(big) + 200)},
    )

    assert response.status_code == 413


def test_upload_document_empty_file_400(route_client, monkeypatch, patch_documents_helpers) -> None:
    response = route_client().post(
        "/v1/collections/docs/documents",
        files={"file": ("x.txt", io.BytesIO(b""), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File is empty"


def test_upload_document_invalid_metadata_schema(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    def bad_meta(_collection, _meta):
        raise ValueError("missing tenant")

    monkeypatch.setattr(documents, "prepare_document_metadata", bad_meta)

    response = route_client().post(
        "/v1/collections/docs/documents",
        files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400
    assert "metadata:" in response.json()["detail"]


def test_upload_document_dedup_returns_existing(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    existing = _document_row()
    session = FakeSession(scalar_values=[existing])

    response = route_client(session=session).post(
        "/v1/collections/docs/documents",
        files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 201
    assert response.json()["deduped"] is True


def test_list_documents_returns_paginated(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    docs = [_document_row(), _document_row()]
    session = FakeSession(scalars_values=[docs], scalar_values=[2])

    response = route_client(session=session).get(
        "/v1/collections/docs/documents?status=ready&limit=5"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["documents"]) == 2


def test_list_documents_batches_live_progress_for_active_docs_only(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents
    from bigrag.services.event_bus import IngestionEvent

    ready_doc = _document_row(status="ready")
    processing_doc = _document_row(status="processing")
    failed_doc = _document_row(status="failed", error_message="bad parse")
    session = FakeSession(
        scalars_values=[[ready_doc, processing_doc, failed_doc]],
        scalar_values=[3],
    )

    async def fail_latest(_doc_id):
        raise AssertionError("latest should not be called for list_documents")

    async def fake_latest_many(doc_ids):
        assert doc_ids == [str(processing_doc.id)]
        return {
            str(processing_doc.id): IngestionEvent(
                document_id=str(processing_doc.id),
                collection_name="docs",
                step="embedding",
                status="processing",
                message="Embedding chunks",
                progress=0.5,
            )
        }

    monkeypatch.setattr(documents.event_bus, "latest", fail_latest)
    monkeypatch.setattr(documents.event_bus, "latest_many", fake_latest_many)

    response = route_client(session=session).get("/v1/collections/docs/documents?limit=1000")

    assert response.status_code == 200
    body = response.json()
    assert body["documents"][0]["progress"]["status"] == "complete"
    assert body["documents"][1]["progress"]["message"] == "Embedding chunks"
    assert body["documents"][2]["progress"]["status"] == "failed"


def test_get_document_invalid_uuid_returns_404(route_client, patch_documents_helpers) -> None:
    response = route_client().get("/v1/collections/docs/documents/not-a-uuid")

    assert response.status_code == 404


def test_get_document_not_found(route_client, patch_documents_helpers) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).get(f"/v1/collections/docs/documents/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_document_happy_path(route_client, patch_documents_helpers) -> None:
    doc = _document_row()
    session = FakeSession(scalar_values=[doc])

    response = route_client(session=session).get(f"/v1/collections/docs/documents/{doc.id}")

    assert response.status_code == 200
    assert response.json()["filename"] == "f.txt"


def test_delete_document_not_found(route_client, patch_documents_helpers) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).delete(
        f"/v1/collections/docs/documents/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_delete_document_happy_path(route_client, monkeypatch, patch_documents_helpers) -> None:
    from bigrag.routers import documents

    async def cancel(_ids):
        return None

    async def delete_vs(*_args, **_kwargs):
        return None

    async def recount(*_args, **_kwargs):
        return None

    class FakeStorage:
        async def delete(self, _path):
            return None

    monkeypatch.setattr(documents.ingestion_queue, "cancel_documents", cancel)
    monkeypatch.setattr(documents.vector_store, "delete_by_document", delete_vs)
    monkeypatch.setattr(documents, "recount_collection_documents", recount)
    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())

    doc = _document_row()
    session = FakeSession(scalar_values=[doc])
    response = route_client(session=session).delete(f"/v1/collections/docs/documents/{doc.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Document deleted"


def test_reprocess_document_not_found(route_client, patch_documents_helpers) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).post(
        f"/v1/collections/docs/documents/{uuid.uuid4()}/reprocess"
    )

    assert response.status_code == 404


def test_reprocess_document_file_missing_400(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    class FakeStorage:
        async def exists(self, _path):
            return False

    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())

    doc = _document_row()
    session = FakeSession(scalar_values=[doc])

    response = route_client(session=session).post(
        f"/v1/collections/docs/documents/{doc.id}/reprocess"
    )

    assert response.status_code == 400
    assert "no longer exists" in response.json()["detail"]


def test_reprocess_document_happy_path(route_client, monkeypatch, patch_documents_helpers) -> None:
    from bigrag.routers import documents

    class FakeStorage:
        async def exists(self, _path):
            return True

    async def cancel(_ids):
        return None

    async def delete_vs(*_args, **_kwargs):
        return None

    async def enqueue(_job):
        return None

    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())
    monkeypatch.setattr(documents.ingestion_queue, "cancel_documents", cancel)
    monkeypatch.setattr(documents.vector_store, "delete_by_document", delete_vs)
    monkeypatch.setattr(documents.ingestion_queue, "enqueue", enqueue)
    monkeypatch.setattr(
        documents, "create_ingestion_job", lambda **kwargs: {"id": kwargs["document_id"]}
    )

    doc = _document_row()
    session = FakeSession(scalar_values=[doc])

    response = route_client(session=session).post(
        f"/v1/collections/docs/documents/{doc.id}/reprocess"
    )

    assert response.status_code == 200
    assert "reprocessing" in response.json()["message"]


def test_get_document_chunks_not_found(route_client, patch_documents_helpers) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).get(
        f"/v1/collections/docs/documents/{uuid.uuid4()}/chunks"
    )

    assert response.status_code == 404


def test_get_document_chunks_happy_path(route_client, monkeypatch, patch_documents_helpers) -> None:
    from bigrag.routers import documents

    async def fake_chunks(*_args, **_kwargs):
        return ([{"text": "a", "index": 0}], 1)

    monkeypatch.setattr(documents.vector_store, "get_chunks", fake_chunks)

    session = FakeSession(scalar_values=[uuid.uuid4()])
    doc_id = uuid.uuid4()

    response = route_client(session=session).get(f"/v1/collections/docs/documents/{doc_id}/chunks")

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_download_document_file_not_found(route_client, patch_documents_helpers) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).get(
        f"/v1/collections/docs/documents/{uuid.uuid4()}/file"
    )

    assert response.status_code == 404


def test_download_document_file_missing_in_storage(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    class FakeStorage:
        async def exists(self, _path):
            return False

    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())

    doc = _document_row()
    session = FakeSession(scalar_values=[doc])

    response = route_client(session=session).get(f"/v1/collections/docs/documents/{doc.id}/file")

    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]


def test_download_document_file_happy_path(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    class FakeStorage:
        async def exists(self, _path):
            return True

        async def get(self, _path):
            return b"some bytes"

    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())

    doc = _document_row(filename="file with spaces.txt", file_type="txt")
    session = FakeSession(scalar_values=[doc])

    response = route_client(session=session).get(f"/v1/collections/docs/documents/{doc.id}/file")

    assert response.status_code == 200
    assert response.content == b"some bytes"
    assert "filename" in response.headers["content-disposition"]


def test_batch_upload_too_many_files(route_client, patch_documents_helpers) -> None:
    files = [("files", (f"f{i}.txt", io.BytesIO(b"x"), "text/plain")) for i in range(101)]
    response = route_client().post(
        "/v1/collections/docs/documents/batch/upload",
        files=files,
    )

    assert response.status_code == 400


def test_batch_status_too_many(route_client, patch_documents_helpers) -> None:
    response = route_client().post(
        "/v1/collections/docs/documents/batch/status",
        json={"document_ids": [str(uuid.uuid4()) for _ in range(101)]},
    )

    assert response.status_code == 400


def test_batch_status_happy_path(route_client, patch_documents_helpers) -> None:
    docs = [_document_row(), _document_row()]
    session = FakeSession(scalars_values=[docs])

    response = route_client(session=session).post(
        "/v1/collections/docs/documents/batch/status",
        json={"document_ids": [str(d.id) for d in docs]},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_batch_get_too_many(route_client, patch_documents_helpers) -> None:
    response = route_client().post(
        "/v1/collections/docs/documents/batch/get",
        json={"document_ids": [str(uuid.uuid4()) for _ in range(101)]},
    )

    assert response.status_code == 400


def test_batch_get_happy_path(route_client, patch_documents_helpers) -> None:
    docs = [_document_row()]
    session = FakeSession(scalars_values=[docs])

    response = route_client(session=session).post(
        "/v1/collections/docs/documents/batch/get",
        json={"document_ids": [str(docs[0].id)]},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_batch_delete_too_many(route_client, patch_documents_helpers) -> None:
    response = route_client().post(
        "/v1/collections/docs/documents/batch/delete",
        json={"document_ids": [str(uuid.uuid4()) for _ in range(101)]},
    )

    assert response.status_code == 400


def test_batch_delete_records_errors_for_missing(
    route_client, monkeypatch, patch_documents_helpers
) -> None:
    from bigrag.routers import documents

    async def cancel(_ids):
        return None

    async def delete_vs(*_args, **_kwargs):
        return None

    async def recount(*_args, **_kwargs):
        return None

    class FakeStorage:
        async def delete(self, _path):
            return None

    monkeypatch.setattr(documents.ingestion_queue, "cancel_documents", cancel)
    monkeypatch.setattr(documents.vector_store, "delete_by_document", delete_vs)
    monkeypatch.setattr(documents, "recount_collection_documents", recount)
    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())

    doc = _document_row()
    missing_id = str(uuid.uuid4())
    session = FakeSession(scalars_values=[[doc]])

    response = route_client(session=session).post(
        "/v1/collections/docs/documents/batch/delete",
        json={"document_ids": [str(doc.id), missing_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] == 1
    assert any(e["document_id"] == missing_id for e in body["errors"])
