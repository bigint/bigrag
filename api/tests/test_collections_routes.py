from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from conftest import FakeSession, now, row
from sqlalchemy.exc import IntegrityError


def collection_row(**overrides):
    value = {
        "id": uuid.uuid4(),
        "name": "docs",
        "description": "Docs",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "dimension": 1536,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_strategy": "paragraph",
        "index_type": "HNSW",
        "tenant_field": None,
        "metadata_schema": None,
        "document_count": 2,
        "embedding_api_key": "sk",
        "embedding_base_url": None,
        "embedding_preset_id": None,
        "reranking_enabled": False,
        "reranking_model": "rerank-v3.5",
        "reranking_api_key": None,
        "default_top_k": 10,
        "default_min_score": None,
        "default_search_mode": "semantic",
        "meta": {},
        "created_at": now(),
        "updated_at": now(),
    }
    value.update(overrides)
    return row(**value)


@dataclass
class RefreshingSession(FakeSession):
    refresh_overrides: dict[str, Any] = field(default_factory=dict)
    integrity_on_commit: bool = False

    async def commit(self) -> None:
        if self.integrity_on_commit:
            raise IntegrityError("stmt", {}, Exception("dup"))
        self.commits += 1

    async def rollback(self) -> None:
        return None

    async def refresh(self, item: Any) -> None:
        for key, value in self.refresh_overrides.items():
            setattr(item, key, value)
        self.refreshed.append(item)


@pytest.fixture
def patch_create_collection_externals(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import collections

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_base_url": None,
            "embedding_api_key": "sk",
        }

    async def noop_verify(*_args, **_kwargs):
        return None

    class FakeEmbedding:
        dimension = 1536

    def fake_get_embedding_model(**_kwargs):
        return FakeEmbedding()

    async def create_collection_vs(*_args, **_kwargs):
        return None

    async def delete_collection_vs(*_args, **_kwargs):
        return None

    async def invalidate(*_args, **_kwargs):
        return None

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    monkeypatch.setattr(collections, "verify_provider_credentials", noop_verify)
    monkeypatch.setattr("bigrag.services.embedding.get_embedding_model", fake_get_embedding_model)
    monkeypatch.setattr(collections.vector_store, "create_collection", create_collection_vs)
    monkeypatch.setattr(collections.vector_store, "delete_collection", delete_collection_vs)
    monkeypatch.setattr(collections.collection_cache, "invalidate", invalidate)
    monkeypatch.setattr(collections.audit, "record", lambda *a, **k: None)
    return monkeypatch


def test_list_collections_with_name_filter(route_client) -> None:
    client = route_client(
        session=FakeSession(
            scalar_values=[1],
            scalars_values=[[collection_row()]],
        )
    )

    response = client.get("/v1/collections?name=do&limit=10&offset=0")

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_create_collection_conflict_when_name_exists(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[uuid.uuid4()]))

    response = client.post(
        "/v1/collections",
        json={"name": "docs", "embedding_api_key": "sk"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Collection already exists"


def test_create_collection_invalid_preset_id(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post(
        "/v1/collections",
        json={
            "name": "docs",
            "embedding_api_key": "sk",
            "embedding_preset_id": "not-a-uuid",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid embedding_preset_id"


def test_create_collection_preset_not_found(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[None], get_values={}))

    response = client.post(
        "/v1/collections",
        json={
            "name": "docs",
            "embedding_api_key": "sk",
            "embedding_preset_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Embedding preset not found"


def test_create_collection_openai_compatible_requires_base_url(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_base_url": None,
            "embedding_api_key": "sk",
        }

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post(
        "/v1/collections",
        json={
            "name": "docs",
            "embedding_provider": "openai_compatible",
            "embedding_api_key": "sk",
        },
    )

    assert response.status_code == 400
    assert "embedding_base_url is required" in response.json()["detail"]


def test_create_collection_openai_compatible_requires_dimension(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": None,
            "embedding_base_url": "https://example.com",
            "embedding_api_key": "sk",
        }

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post(
        "/v1/collections",
        json={
            "name": "docs",
            "embedding_provider": "openai_compatible",
            "embedding_api_key": "sk",
            "embedding_base_url": "https://example.com",
        },
    )

    assert response.status_code == 400
    assert "dimension is required" in response.json()["detail"]


def test_create_collection_missing_api_key_400(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_base_url": None,
            "embedding_api_key": None,
        }

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post("/v1/collections", json={"name": "docs"})

    assert response.status_code == 400
    assert "API key is required" in response.json()["detail"]


def test_create_collection_credential_check_fails_422(route_client, monkeypatch) -> None:
    from bigrag.routers import collections
    from bigrag.services.credential_check import CredentialCheckError

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_base_url": None,
            "embedding_api_key": "sk",
        }

    async def bad_verify(*_args, **_kwargs):
        raise CredentialCheckError("invalid_key", "invalid key")

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    monkeypatch.setattr(collections, "verify_provider_credentials", bad_verify)
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post(
        "/v1/collections",
        json={"name": "docs", "embedding_api_key": "sk"},
    )

    assert response.status_code == 422
    assert "rejected" in response.json()["detail"]


def test_create_collection_embedding_import_error_400(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_get_values(_keys):
        return {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_dimension": 1536,
            "embedding_base_url": None,
            "embedding_api_key": "sk",
        }

    async def noop_verify(*_args, **_kwargs):
        return None

    def fail_embedding(**_kwargs):
        raise ValueError("bad config")

    monkeypatch.setattr(collections, "get_values", fake_get_values)
    monkeypatch.setattr(collections, "verify_provider_credentials", noop_verify)
    monkeypatch.setattr("bigrag.services.embedding.get_embedding_model", fail_embedding)
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post(
        "/v1/collections",
        json={"name": "docs", "embedding_api_key": "sk"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "bad config"


def test_create_collection_happy_path(route_client, patch_create_collection_externals) -> None:
    new_id = uuid.uuid4()
    session = RefreshingSession(
        scalar_values=[None],
        refresh_overrides={
            "id": new_id,
            "created_at": now(),
            "updated_at": now(),
            "document_count": 0,
        },
    )
    client = route_client(session=session)

    response = client.post(
        "/v1/collections",
        json={
            "name": "docs",
            "embedding_api_key": "sk",
            "description": "Docs",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "docs"
    assert body["embedding_provider"] == "openai"
    assert session.commits == 1
    assert len(session.added) == 1


def test_create_collection_integrity_error_returns_409(
    route_client, patch_create_collection_externals
) -> None:
    session = RefreshingSession(scalar_values=[None], integrity_on_commit=True)
    client = route_client(session=session)

    response = client.post(
        "/v1/collections",
        json={"name": "docs", "embedding_api_key": "sk"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Collection already exists"


def test_reembed_collection_404(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[None]))

    response = client.post("/v1/collections/missing/reembed")

    assert response.status_code == 404


def test_reembed_collection_queues_documents(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    col = collection_row()

    async def cancel_collection(_name):
        return 0

    async def enqueue(_job):
        return None

    async def invalidate(*_args, **_kwargs):
        return None

    monkeypatch.setattr(collections.ingestion_queue, "enqueue", enqueue)
    monkeypatch.setattr(collections, "invalidate_collection_query_cache", invalidate)
    monkeypatch.setattr(collections.audit, "record", lambda *a, **k: None)
    monkeypatch.setattr(
        collections,
        "create_ingestion_job",
        lambda **kwargs: {"document_id": kwargs["document_id"]},
    )

    session = FakeSession(
        scalar_values=[col],
        execute_values=[[(uuid.uuid4(), "path/a"), (uuid.uuid4(), "path/b")], [], []],
    )
    client = route_client(session=session)

    response = client.post(f"/v1/collections/{col.name}/reembed")

    assert response.status_code == 200
    assert "Queued 2" in response.json()["message"]


def test_get_collection_404(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).get(
        "/v1/collections/missing"
    )

    assert response.status_code == 404


def test_get_collection_happy_path(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[collection_row()]))

    response = client.get("/v1/collections/docs")

    assert response.status_code == 200
    assert response.json()["name"] == "docs"


def test_get_collection_stats_404(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).get(
        "/v1/collections/missing/stats"
    )

    assert response.status_code == 404


def test_get_collection_stats_happy_path(route_client) -> None:
    stats = row(
        total_chunks=100,
        total_tokens=1000,
        total_size=2000,
        document_count=5,
        ready=4,
        pending=0,
        processing=1,
        failed=0,
    )
    session = FakeSession(scalar_values=[uuid.uuid4()], execute_values=[[stats]])

    response = route_client(session=session).get("/v1/collections/docs/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["document_count"] == 5
    assert body["total_chunks"] == 100
    assert body["status_counts"]["ready"] == 4


def test_update_collection_404(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).put(
        "/v1/collections/missing",
        json={"description": "x"},
    )

    assert response.status_code == 404


def test_update_collection_rejects_empty_api_key(route_client) -> None:
    client = route_client(session=FakeSession(scalar_values=[collection_row()]))

    response = client.put(
        "/v1/collections/docs",
        json={"embedding_api_key": "   "},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_update_collection_full_field_set(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(collections, "verify_provider_credentials", noop)
    monkeypatch.setattr(collections.collection_cache, "invalidate", noop)
    monkeypatch.setattr(collections, "invalidate_collection_query_cache", noop)
    monkeypatch.setattr(collections.audit, "record", lambda *a, **k: None)

    col = collection_row(embedding_preset_id=uuid.uuid4())
    session = FakeSession(scalar_values=[col])
    client = route_client(session=session)

    response = client.put(
        "/v1/collections/docs",
        json={
            "description": "new",
            "metadata": {"k": "v"},
            "embedding_api_key": "new-key",
            "reranking_enabled": True,
            "reranking_model": "rerank-2",
            "reranking_api_key": "rk",
            "default_top_k": 5,
            "default_min_score": 0.5,
            "default_search_mode": "hybrid",
            "chunk_strategy": "recursive",
            "metadata_schema": {"type": "object"},
        },
    )

    assert response.status_code == 200
    assert col.description == "new"
    assert col.embedding_api_key == "new-key"
    assert col.embedding_preset_id is None
    assert col.reranking_enabled is True
    assert col.default_top_k == 5


def test_delete_collection_404(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).delete(
        "/v1/collections/missing"
    )

    assert response.status_code == 404


def test_delete_collection_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def cancel_collection(_name):
        return 3

    async def delete_vs(*_args, **_kwargs):
        return None

    class FakeStorage:
        async def delete_prefix(self, _prefix):
            return 7

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(collections.ingestion_queue, "cancel_collection", cancel_collection)
    monkeypatch.setattr(collections.vector_store, "delete_collection", delete_vs)
    monkeypatch.setattr("bigrag.services.storage.get_storage", lambda: FakeStorage())
    monkeypatch.setattr(collections.collection_cache, "invalidate", noop)
    monkeypatch.setattr(collections, "invalidate_collection_query_cache", noop)
    monkeypatch.setattr(collections.audit, "record", lambda *a, **k: None)

    session = FakeSession(scalar_values=[collection_row()])
    client = route_client(session=session)

    response = client.delete("/v1/collections/docs")

    assert response.status_code == 200
    assert "deleted" in response.json()["message"]
    assert session.commits == 1


def test_truncate_collection_404(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).post(
        "/v1/collections/missing/truncate"
    )

    assert response.status_code == 404


def test_truncate_collection_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def cancel_collection(_name):
        return 0

    async def delete_vs(*_args, **_kwargs):
        return None

    class FakeStorage:
        async def delete_prefix(self, _prefix):
            return 0

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(collections.ingestion_queue, "cancel_collection", cancel_collection)
    monkeypatch.setattr(collections.vector_store, "delete_collection", delete_vs)
    monkeypatch.setattr("bigrag.services.storage.get_storage", lambda: FakeStorage())
    monkeypatch.setattr(collections.collection_cache, "invalidate", noop)
    monkeypatch.setattr(collections, "invalidate_collection_query_cache", noop)
    monkeypatch.setattr(collections.audit, "record", lambda *a, **k: None)

    session = FakeSession(scalar_values=[uuid.uuid4()], execute_values=[[], []])
    client = route_client(session=session)

    response = client.post("/v1/collections/docs/truncate")

    assert response.status_code == 200
    assert "truncated" in response.json()["message"]


def test_event_token_404_when_collection_missing(route_client) -> None:
    response = route_client(session=FakeSession(scalar_values=[None])).post(
        "/v1/collections/missing/events/token"
    )

    assert response.status_code == 404


def test_event_token_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_token(_user, _name):
        return "tok-123"

    monkeypatch.setattr(collections, "create_event_token", fake_token)
    client = route_client(session=FakeSession(scalar_values=[uuid.uuid4()]))

    response = client.post("/v1/collections/docs/events/token")

    assert response.status_code == 200
    assert response.json()["token"] == "tok-123"
    assert response.json()["expires_in"] > 0


def test_event_token_runtime_error_returns_503(route_client, monkeypatch) -> None:
    from bigrag.routers import collections

    async def fake_token(_user, _name):
        raise RuntimeError("redis down")

    monkeypatch.setattr(collections, "create_event_token", fake_token)
    client = route_client(session=FakeSession(scalar_values=[uuid.uuid4()]))

    response = client.post("/v1/collections/docs/events/token")

    assert response.status_code == 503
    assert response.json()["detail"] == "redis down"
