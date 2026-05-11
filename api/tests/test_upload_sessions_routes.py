from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import FakeSession


def _session_row(
    id_=None, status: str = "preparing", total_files: int = 3, **overrides
) -> SimpleNamespace:
    now = datetime.now(UTC)
    base = {
        "id": id_ or uuid.uuid4(),
        "collection_id": uuid.uuid4(),
        "collection_name": "docs",
        "status": status,
        "total_files": total_files,
        "total_bytes": 1024,
        "uploaded_files": 0,
        "queued_files": 0,
        "completed_files": 0,
        "failed_files": 0,
        "canceled_files": 0,
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "meta": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def patch_upload_session_helpers(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    def fake_embedding(_collection):
        return object()

    async def fake_get_values(keys):
        return {key: 100 for key in keys}

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(upload_sessions, "get_embedding_model_for", fake_embedding)
    monkeypatch.setattr(upload_sessions, "get_values", fake_get_values)
    monkeypatch.setattr(upload_sessions.audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(upload_sessions.collection_cache, "invalidate", noop)
    monkeypatch.setattr(upload_sessions, "invalidate_collection_query_cache", noop)
    return monkeypatch


def test_create_upload_session_collection_not_found(route_client, monkeypatch) -> None:
    from fastapi import HTTPException

    from bigrag.routers import upload_sessions

    async def missing(_name):
        raise HTTPException(status_code=404, detail="Collection not found")

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", missing)

    response = route_client().post(
        "/v1/collections/missing/upload-sessions",
        json={"total_files": 1, "total_bytes": 100},
    )

    assert response.status_code == 404


def test_create_upload_session_embedding_error(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    def fail_embedding(_collection):
        raise ValueError("bad model")

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(upload_sessions, "get_embedding_model_for", fail_embedding)

    response = route_client().post(
        "/v1/collections/docs/upload-sessions",
        json={"total_files": 1, "total_bytes": 100},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad model"


def test_create_upload_session_too_many_files(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    async def fake_get_values(_keys):
        return {"max_upload_session_files": 5, "max_upload_session_size_mb": 100}

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(upload_sessions, "get_embedding_model_for", lambda _c: object())
    monkeypatch.setattr(upload_sessions, "get_values", fake_get_values)

    response = route_client().post(
        "/v1/collections/docs/upload-sessions",
        json={"total_files": 100, "total_bytes": 100},
    )

    assert response.status_code == 400
    assert "Maximum 5 files" in response.json()["detail"]


def test_create_upload_session_too_large(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    async def fake_get_values(_keys):
        return {"max_upload_session_files": 100, "max_upload_session_size_mb": 1}

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(upload_sessions, "get_embedding_model_for", lambda _c: object())
    monkeypatch.setattr(upload_sessions, "get_values", fake_get_values)

    response = route_client().post(
        "/v1/collections/docs/upload-sessions",
        json={"total_files": 1, "total_bytes": 10 * 1024 * 1024},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_create_upload_session_invalid_metadata(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    async def fake_get_values(_keys):
        return {"max_upload_session_files": 100, "max_upload_session_size_mb": 100}

    def bad_metadata(_collection, _meta):
        raise ValueError("metadata is bad")

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    monkeypatch.setattr(upload_sessions, "get_embedding_model_for", lambda _c: object())
    monkeypatch.setattr(upload_sessions, "get_values", fake_get_values)
    monkeypatch.setattr(upload_sessions, "prepare_document_metadata", bad_metadata)

    response = route_client().post(
        "/v1/collections/docs/upload-sessions",
        json={"total_files": 1, "total_bytes": 100, "metadata": {"k": "v"}},
    )

    assert response.status_code == 400
    assert "metadata:" in response.json()["detail"]


def test_get_upload_session_bad_uuid_returns_404(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)

    response = route_client().get("/v1/collections/docs/upload-sessions/not-a-uuid")

    assert response.status_code == 404


def test_get_upload_session_not_found(route_client, monkeypatch) -> None:
    from bigrag.routers import upload_sessions

    async def fake_get_collection(name):
        return {"id": uuid.uuid4(), "name": name, "tenant_field": None}

    monkeypatch.setattr(upload_sessions, "get_collection_or_404", fake_get_collection)
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).get(
        f"/v1/collections/docs/upload-sessions/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_get_upload_session_happy_path(route_client, patch_upload_session_helpers) -> None:
    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id)
    session = FakeSession(scalar_values=[row], execute_values=[[]])

    response = route_client(session=session).get(f"/v1/collections/docs/upload-sessions/{sess_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(sess_id)


def test_complete_upload_session_returns_409_when_canceled(
    route_client, patch_upload_session_helpers
) -> None:
    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id, status="canceled")
    session = FakeSession(scalar_values=[row])

    response = route_client(session=session).post(
        f"/v1/collections/docs/upload-sessions/{sess_id}/complete"
    )

    assert response.status_code == 409


def test_complete_upload_session_happy_path(route_client, patch_upload_session_helpers) -> None:
    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id)
    session = FakeSession(scalar_values=[row], execute_values=[[]])

    response = route_client(session=session).post(
        f"/v1/collections/docs/upload-sessions/{sess_id}/complete"
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(sess_id)


def test_cancel_upload_session_cancels_queued_items(
    route_client, monkeypatch, patch_upload_session_helpers
) -> None:
    from bigrag.routers import upload_sessions

    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id)

    canceled_docs: list[Any] = []

    async def fake_cancel(doc_ids):
        canceled_docs.extend(doc_ids)
        return len(doc_ids)

    monkeypatch.setattr(upload_sessions.ingestion_queue, "cancel_documents", fake_cancel)

    queued_item = SimpleNamespace(
        id=uuid.uuid4(),
        client_item_id="c-1",
        filename="f.txt",
        file_type="txt",
        file_size=10,
        content_hash=None,
        document_id=uuid.uuid4(),
        status="queued",
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session = FakeSession(
        scalar_values=[row],
        execute_values=[[(queued_item, "pending", None)]],
    )

    response = route_client(session=session).post(
        f"/v1/collections/docs/upload-sessions/{sess_id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Upload session canceled"
    assert len(canceled_docs) == 1
    assert queued_item.status == "canceled"
    assert row.status == "canceled"


def test_upload_session_file_returns_409_when_closed(
    route_client, monkeypatch, patch_upload_session_helpers
) -> None:
    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id, status="complete")
    session = FakeSession(scalar_values=[row])

    response = route_client(session=session).post(
        f"/v1/collections/docs/upload-sessions/{sess_id}/files",
        files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")},
    )

    assert response.status_code == 409


def test_upload_session_file_returns_400_when_count_complete(
    route_client, monkeypatch, patch_upload_session_helpers
) -> None:
    sess_id = uuid.uuid4()
    row = _session_row(id_=sess_id, total_files=1)
    existing_item = SimpleNamespace(
        id=uuid.uuid4(),
        client_item_id="other",
        filename="f1.txt",
        file_type="txt",
        file_size=10,
        content_hash="h1",
        document_id=uuid.uuid4(),
        status="queued",
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session = FakeSession(
        scalar_values=[row, None],
        execute_values=[[(existing_item, "pending", None)]],
    )

    response = route_client(session=session).post(
        f"/v1/collections/docs/upload-sessions/{sess_id}/files",
        files={"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")},
        data={"client_item_id": "new-one"},
    )

    assert response.status_code == 400
    assert "already complete" in response.json()["detail"]
