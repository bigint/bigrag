from __future__ import annotations

import uuid

from conftest import FakeSession, now, row, user_principal

from bigrag import config as config_module
from bigrag.config import Settings
from bigrag.db.models import InstanceSetting
from bigrag.services import runtime_settings
from bigrag.services.runtime_setting_specs import REGISTRY


def cache_runtime_defaults(**overrides):
    config_module.settings = Settings()
    values = runtime_settings.default_values(list(REGISTRY))
    values.update(overrides)
    runtime_settings.set_runtime_settings_cache(values)


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
    from bigrag.routers import documents

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
    from bigrag.routers import documents

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
    from bigrag.routers import webhooks

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
    cache_runtime_defaults()

    response = route_client().post(
        "/v1/admin/settings/test",
        json={"values": {"session_cookie_secure": True}},
    )

    assert response.status_code == 200
    assert response.json()["checked"] == ["session_cookie_secure"]


def test_instance_settings_test_rejects_unknown_key(route_client) -> None:
    cache_runtime_defaults()

    response = route_client().post(
        "/v1/admin/settings/test",
        json={"values": {"missing": True}},
    )

    assert response.status_code == 400
    assert "Unknown setting" in response.json()["detail"]


def test_instance_settings_update_applies_live_values(route_client, monkeypatch) -> None:
    from bigrag.services import runtime_settings_apply

    cache_runtime_defaults()
    resized: list[int] = []

    async def resize_workers(value: int) -> None:
        resized.append(value)

    monkeypatch.setattr(runtime_settings_apply.ingestion_queue, "resize_workers", resize_workers)
    session = FakeSession(scalars_values=[[], []])
    client = route_client(session=session)

    response = client.put(
        "/v1/admin/settings",
        json={"values": {"ingestion_workers": 2, "session_cookie_secure": True}},
    )

    assert response.status_code == 200
    assert session.commits == 1
    assert resized == [2]
    assert runtime_settings.sync_value("ingestion_workers") == 2
    assert client.app.state.settings.ingestion_workers == 2
    assert client.app.state.settings.session_cookie_secure is True


def test_instance_settings_reset_applies_live_defaults(route_client) -> None:
    cache_runtime_defaults(session_cookie_secure=True)
    session = FakeSession(
        scalars_values=[[InstanceSetting(key="session_cookie_secure", value=True)], []]
    )
    client = route_client(session=session)

    response = client.post("/v1/admin/settings/reset", json={"keys": ["session_cookie_secure"]})

    assert response.status_code == 200
    assert session.commits == 1
    assert runtime_settings.sync_value("session_cookie_secure") is False
    assert client.app.state.settings.session_cookie_secure is False


def test_instance_settings_vector_failure_does_not_commit(route_client, monkeypatch) -> None:
    from bigrag.services import runtime_settings_apply

    cache_runtime_defaults()

    async def fail_vector(_values):
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr(runtime_settings_apply, "_prepare_vector_backend", fail_vector)
    session = FakeSession(scalars_values=[[], []])
    client = route_client(session=session)

    response = client.put(
        "/v1/admin/settings",
        json={"values": {"vector_store_provider": "turbopuffer"}},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "vector unavailable"
    assert session.commits == 0


def test_instance_settings_storage_and_vector_swap_live(route_client, monkeypatch) -> None:
    from bigrag.services import runtime_settings_apply

    cache_runtime_defaults()
    replaced_storage = []

    class FakeStorage:
        async def close(self):
            return None

    class FakeActiveVectorStore:
        def __init__(self):
            self.replaced = None

        async def replace_with(self, other):
            self.replaced = other

    class FakeVectorStore:
        async def close(self):
            return None

    storage_backend = FakeStorage()
    vector_backend = FakeVectorStore()
    active_vector = FakeActiveVectorStore()

    async def prepare_storage(_app, _values):
        return storage_backend

    async def replace_storage(backend):
        replaced_storage.append(backend)
        return backend

    async def prepare_vector(_values):
        return vector_backend

    monkeypatch.setattr(runtime_settings_apply, "_prepare_storage_backend", prepare_storage)
    monkeypatch.setattr(runtime_settings_apply, "_prepare_vector_backend", prepare_vector)
    monkeypatch.setattr(runtime_settings_apply, "replace_storage_backend", replace_storage)
    monkeypatch.setattr(runtime_settings_apply, "vector_store", active_vector)
    session = FakeSession(scalars_values=[[], []])
    client = route_client(session=session)

    response = client.put(
        "/v1/admin/settings",
        json={"values": {"storage_backend": "local", "vector_store_provider": "turbopuffer"}},
    )

    assert response.status_code == 200
    assert replaced_storage == [storage_backend]
    assert active_vector.replaced is vector_backend
    assert client.app.state.storage is storage_backend
    assert client.app.state.vector_store is active_vector


def test_instance_settings_embedding_concurrency_resets_semaphores(
    route_client,
    monkeypatch,
) -> None:
    from bigrag.services import runtime_settings_apply

    cache_runtime_defaults()
    reset_calls = 0

    def reset_embedding_semaphores() -> None:
        nonlocal reset_calls
        reset_calls += 1

    monkeypatch.setattr(
        runtime_settings_apply,
        "reset_embedding_semaphores",
        reset_embedding_semaphores,
    )
    session = FakeSession(scalars_values=[[], []])
    client = route_client(session=session)

    response = client.put(
        "/v1/admin/settings",
        json={"values": {"embedding_concurrency": 3}},
    )

    assert response.status_code == 200
    assert reset_calls == 1
