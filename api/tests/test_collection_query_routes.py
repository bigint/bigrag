from __future__ import annotations

import uuid
from types import SimpleNamespace

from conftest import FakeSession, now, row


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


def test_list_collections_uses_harness_session(route_client) -> None:
    client = route_client(
        session=FakeSession(
            scalar_values=[1],
            scalars_values=[[collection_row()]],
        )
    )

    response = client.get("/v1/collections")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["collections"][0]["name"] == "docs"


def test_list_collections_rejects_unauthenticated(route_client) -> None:
    response = route_client(unauthenticated=True).get("/v1/collections")

    assert response.status_code == 401


def test_create_collection_rejects_unsupported_provider(route_client, monkeypatch) -> None:
    from rag_computer.routers import collections

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
            "embedding_provider": "unknown",
            "embedding_api_key": "sk",
        },
    )

    assert response.status_code == 400
    assert "Unsupported embedding provider" in response.json()["detail"]


def test_query_collection_success_sets_response_shape(route_client, monkeypatch) -> None:
    from rag_computer.routers import query

    async def fake_get_collection_or_404(_name):
        return {
            "id": "col",
            "default_top_k": 3,
            "default_min_score": None,
            "default_search_mode": "semantic",
            "tenant_field": None,
        }

    async def fake_retrieve(**_kwargs):
        return SimpleNamespace(
            results=[
                {
                    "id": "chunk",
                    "text": "hello",
                    "score": 0.9,
                    "document_id": "doc",
                    "chunk_index": 0,
                    "metadata": {"page_no": 1},
                }
            ],
            embed_ms=1,
            search_ms=2,
            rerank_ms=0,
            total_ms=3,
        )

    monkeypatch.setattr(query, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query, "get_embedding_model_for", lambda _collection: object())
    monkeypatch.setattr(query, "get_reranking_config", lambda _collection: None)
    monkeypatch.setattr(query, "retrieve", fake_retrieve)
    monkeypatch.setattr(query.access_log, "set_context", lambda *args, **kwargs: None)

    response = route_client().post("/v1/collections/docs/query", json={"query": "hello"})

    assert response.status_code == 200
    assert response.json()["results"][0]["page_no"] == 1
    assert response.json()["timings"]["total_ms"] == 3


def test_query_collection_maps_embedding_errors(route_client, monkeypatch) -> None:
    from rag_computer.routers import query

    async def fake_get_collection_or_404(_name):
        return {"id": "col", "tenant_field": None}

    def fail_get_embedding_model(_collection):
        raise ValueError("bad model")

    monkeypatch.setattr(query, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query, "get_embedding_model_for", fail_get_embedding_model)
    monkeypatch.setattr(query.access_log, "set_context", lambda *args, **kwargs: None)

    response = route_client().post("/v1/collections/docs/query", json={"query": "hello"})

    assert response.status_code == 400
    assert response.json()["detail"] == "bad model"


def test_vector_upsert_enforces_limits(route_client, monkeypatch) -> None:
    from rag_computer.routers import query

    async def fake_get_collection_or_404(_name):
        return {"id": "col", "dimension": 2, "tenant_field": None}

    async def fake_get_values(_keys):
        return {
            "max_vector_upsert_count": 1,
            "max_vector_text_chars": 100,
            "max_vector_metadata_bytes": 100,
        }

    monkeypatch.setattr(query, "get_collection_or_404", fake_get_collection_or_404)
    monkeypatch.setattr(query, "get_values", fake_get_values)
    monkeypatch.setattr(query.access_log, "set_context", lambda *args, **kwargs: None)

    response = route_client().post(
        "/v1/collections/docs/vectors/upsert",
        json={
            "vectors": [
                {"id": "a", "embedding": [1, 2], "text": "a", "metadata": {}},
                {"id": "b", "embedding": [1, 2], "text": "b", "metadata": {}},
            ]
        },
    )

    assert response.status_code == 413
    assert "Too many vectors" in response.json()["detail"]
