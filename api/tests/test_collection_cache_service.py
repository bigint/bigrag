from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from rag_computer.exceptions import NotFoundError
from rag_computer.services import collection_cache


def run(coro):
    return asyncio.run(coro)


class ScalarRows:
    def __init__(self, values) -> None:
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, *, collection=None, preset=None, names=None) -> None:
        self.collection = collection
        self.preset = preset
        self.names = names or []
        self.get_calls = []

    async def scalar(self, _stmt):
        return self.collection

    async def get(self, model, key):
        self.get_calls.append((model, key))
        return self.preset

    async def scalars(self, _stmt):
        return ScalarRows(self.names)


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class FakeRedisCache:
    def __init__(self, value=None) -> None:
        self.value = value
        self.sets = []
        self.deletes = []

    async def get(self, key):
        return self.value

    async def set(self, key, value, ttl=None):
        self.sets.append((key, value, ttl))

    async def delete(self, key):
        self.deletes.append(key)


def get_value(value: int):
    async def fake_get_value(_key):
        return value

    return fake_get_value


def collection(**overrides):
    collection_id = uuid.uuid4()
    now = datetime(2026, 5, 11, tzinfo=UTC)
    value = {
        "id": collection_id,
        "name": "docs",
        "description": "Docs",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_api_key": "sk",
        "embedding_base_url": None,
        "embedding_preset_id": None,
        "dimension": 1536,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_strategy": "paragraph",
        "document_count": 2,
        "default_top_k": 10,
        "default_min_score": None,
        "default_search_mode": "semantic",
        "reranking_enabled": False,
        "reranking_model": "rerank-v3.5",
        "reranking_api_key": None,
        "index_type": "HNSW",
        "tenant_field": None,
        "metadata_schema": None,
        "meta": {"team": "search"},
        "created_at": now,
        "updated_at": now,
    }
    value.update(overrides)
    return SimpleNamespace(**value)


def test_cached_collection_is_deserialized_without_database(monkeypatch) -> None:
    collection_id = uuid.uuid4()
    cached = {
        "id": str(collection_id),
        "name": "docs",
        "created_at": "2026-05-11T00:00:00+00:00",
        "updated_at": "2026-05-11T00:00:01+00:00",
    }
    cache = FakeRedisCache(cached)

    monkeypatch.setattr(collection_cache, "redis_cache", cache)

    result = run(collection_cache.get_or_404("docs"))

    assert result["id"] == collection_id
    assert result["created_at"] == datetime(2026, 5, 11, tzinfo=UTC)
    assert result["updated_at"] == datetime(2026, 5, 11, 0, 0, 1, tzinfo=UTC)


def test_get_or_404_serializes_database_collection_and_preset(monkeypatch) -> None:
    preset_id = uuid.uuid4()
    row = collection(embedding_preset_id=preset_id, embedding_api_key=None)
    preset = SimpleNamespace(api_key="preset-key", base_url="https://api.example.com")
    session = FakeSession(collection=row, preset=preset)
    cache = FakeRedisCache()

    monkeypatch.setattr(collection_cache, "redis_cache", cache)
    monkeypatch.setattr(
        collection_cache,
        "session_factory",
        lambda: lambda: FakeSessionContext(session),
    )
    monkeypatch.setattr(collection_cache, "get_value", get_value(30))

    result = run(collection_cache.get_or_404("docs"))

    assert result["id"] == str(row.id)
    assert result["metadata"] == {"team": "search"}
    assert result["embedding_preset_id"] == str(preset_id)
    assert result["embedding_preset_api_key"] == "preset-key"
    assert result["embedding_preset_base_url"] == "https://api.example.com"
    assert cache.sets == [("collection:docs", result, 30)]


def test_get_or_404_skips_cache_when_ttl_is_zero(monkeypatch) -> None:
    row = collection()
    cache = FakeRedisCache()

    monkeypatch.setattr(collection_cache, "redis_cache", cache)
    monkeypatch.setattr(
        collection_cache,
        "session_factory",
        lambda: lambda: FakeSessionContext(FakeSession(collection=row)),
    )
    monkeypatch.setattr(collection_cache, "get_value", get_value(0))

    assert run(collection_cache.get_or_404("docs"))["name"] == "docs"
    assert cache.sets == []


def test_get_or_404_raises_not_found(monkeypatch) -> None:
    monkeypatch.setattr(collection_cache, "redis_cache", FakeRedisCache())
    monkeypatch.setattr(
        collection_cache,
        "session_factory",
        lambda: lambda: FakeSessionContext(FakeSession(collection=None)),
    )

    with pytest.raises(NotFoundError, match="Collection not found: missing"):
        run(collection_cache.get_or_404("missing"))


def test_invalidate_deletes_single_and_preset_collections(monkeypatch) -> None:
    cache = FakeRedisCache()
    monkeypatch.setattr(collection_cache, "redis_cache", cache)

    run(collection_cache.invalidate("docs"))

    assert cache.deletes == ["collection:docs"]

    session = FakeSession(names=["docs", "api"])
    monkeypatch.setattr(
        collection_cache,
        "session_factory",
        lambda: lambda: FakeSessionContext(session),
    )

    run(collection_cache.invalidate_for_preset(uuid.uuid4()))

    assert cache.deletes == ["collection:docs", "collection:docs", "collection:api"]
