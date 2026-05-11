from __future__ import annotations

import uuid

from conftest import FakeSession, now, row, user_principal


def document_row(collection_id: uuid.UUID, **overrides):
    value = {
        "id": uuid.uuid4(),
        "collection_id": collection_id,
        "filename": "note.txt",
        "file_type": "txt",
        "file_size": 5,
        "chunk_count": 1,
        "status": "ready",
        "error_message": None,
        "meta": {},
        "content_hash": "hash",
        "created_at": now(),
        "updated_at": now(),
    }
    value.update(overrides)
    return row(**value)


def test_list_documents_success(route_client, monkeypatch) -> None:
    from rag_computer.routers import documents

    collection_id = uuid.uuid4()

    async def fake_get_collection_or_404(_name):
        return {"id": collection_id, "tenant_field": None}

    class FakeBus:
        async def latest(self, _document_id):
            return None

    monkeypatch.setattr(documents, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(documents, "event_bus", FakeBus())
    client = route_client(
        session=FakeSession(
            scalar_values=[1],
            scalars_values=[[document_row(collection_id)]],
        )
    )

    response = client.get("/v1/collections/docs/documents?status=ready")

    assert response.status_code == 200
    assert response.json()["documents"][0]["filename"] == "note.txt"
    assert response.json()["documents"][0]["progress"]["status"] == "complete"


def test_download_document_file_returns_storage_bytes(route_client, monkeypatch) -> None:
    from rag_computer.routers import documents

    collection_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    doc = document_row(collection_id, id=doc_id, file_path="uploads/note.txt")

    async def fake_get_collection_or_404(_name):
        return {"id": collection_id, "tenant_field": None}

    class FakeStorage:
        async def exists(self, _path):
            return True

        async def get(self, _path):
            return b"hello"

    monkeypatch.setattr(documents, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(documents, "get_storage", lambda: FakeStorage())
    client = route_client(session=FakeSession(scalar_values=[doc]))

    response = client.get(f"/v1/collections/docs/documents/{doc_id}/file")

    assert response.status_code == 200
    assert response.content == b"hello"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


def test_create_webhook_rejects_member_session(route_client) -> None:
    client = route_client(user=user_principal(role="member"))

    response = client.post(
        "/v1/admin/webhooks",
        json={"url": "https://example.com/hook", "events": ["document.ready"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_test_webhook_dispatches(route_client, monkeypatch) -> None:
    from rag_computer.routers import webhooks

    webhook_id = uuid.uuid4()
    webhook = row(
        id=webhook_id,
        url="https://example.com/hook",
        secret="secret",
        events=["document.ready"],
        collections=None,
        description="",
        active=True,
        created_by=None,
        created_at=now(),
        updated_at=now(),
    )

    class FakeDispatcher:
        async def deliver_test(self, payload):
            return {"status": "ok", "status_code": 204, "error": None, "url": payload["url"]}

    monkeypatch.setattr(webhooks, "webhook_dispatcher", FakeDispatcher())
    monkeypatch.setattr(webhooks.audit, "record", lambda *args, **kwargs: None)
    client = route_client(session=FakeSession(get_values={webhook_id: webhook}))

    response = client.post(f"/v1/admin/webhooks/{webhook_id}/test")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["status_code"] == 204


def test_instance_settings_test_validates_values(route_client) -> None:
    response = route_client().post(
        "/admin/settings/test",
        json={"values": {"session_cookie_secure": True}},
    )

    assert response.status_code == 200
    assert response.json()["checked"] == ["session_cookie_secure"]


def test_instance_settings_test_rejects_unknown_key(route_client) -> None:
    response = route_client().post(
        "/admin/settings/test",
        json={"values": {"missing": True}},
    )

    assert response.status_code == 400
    assert "Unknown setting" in response.json()["detail"]
