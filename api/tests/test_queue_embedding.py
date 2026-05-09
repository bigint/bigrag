from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bigrag.services import queue_embedding
from bigrag.services.ingestion_job import IngestionJob


@dataclass
class FakeChunk:
    text: str
    char_start: int
    char_end: int


class FakeEmbeddingCache:
    def __init__(self, cached=None) -> None:
        self.cached = cached or {}
        self.puts = []

    async def get_many(self, texts, provider, model_name, dimension):
        return dict(self.cached)

    async def put_many(self, texts, fresh, provider, model_name, dimension):
        self.puts.append((texts, fresh, provider, model_name, dimension))


class FakeModel:
    def __init__(self, vectors) -> None:
        self.vectors = vectors
        self.calls = []

    async def embed(self, texts):
        self.calls.append(texts)
        return self.vectors


class FakeVectorStore:
    def __init__(self) -> None:
        self.created = []
        self.inserted = []
        self.deleted = []

    async def create_collection(self, collection, dimension, tenant_field=None):
        self.created.append((collection, dimension, tenant_field))

    async def insert(self, **kwargs):
        self.inserted.append(kwargs)
        return len(kwargs["ids"])

    async def delete_by_document(self, collection_name, document_id):
        self.deleted.append((collection_name, document_id))


def _job(**overrides) -> IngestionJob:
    values = {
        "document_id": "11111111-1111-1111-1111-111111111111",
        "file_path": "docs/a.txt",
        "collection_name": "docs",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 2,
        "chunk_size": 400,
        "chunk_overlap": 40,
        "tenant_field": "tenant_id",
        "job_id": "job",
    }
    values.update(overrides)
    return IngestionJob(**values)


def test_embed_with_cache_fetches_unique_missing_texts_and_reuses_duplicates(monkeypatch) -> None:
    async def run() -> None:
        cache = FakeEmbeddingCache({0: [1.0, 1.0]})
        model = FakeModel([[2.0, 2.0]])
        monkeypatch.setattr(queue_embedding, "embedding_cache", cache)
        monkeypatch.setattr(
            queue_embedding,
            "truncate_to_tokens",
            lambda texts, model_name: (texts, 0),
        )

        vectors = await queue_embedding.embed_with_cache(
            ["cached", "missing", "missing"],
            model,
            "openai",
            "model",
            2,
        )

        assert model.calls == [["missing"]]
        assert cache.puts == [(["missing"], [[2.0, 2.0]], "openai", "model", 2)]
        assert vectors == [[1.0, 1.0], [2.0, 2.0], [2.0, 2.0]]

    asyncio.run(run())


def test_embed_with_cache_rejects_provider_vector_count_mismatch(monkeypatch) -> None:
    async def run() -> None:
        monkeypatch.setattr(queue_embedding, "embedding_cache", FakeEmbeddingCache())
        monkeypatch.setattr(
            queue_embedding,
            "truncate_to_tokens",
            lambda texts, model_name: (texts, 0),
        )

        try:
            await queue_embedding.embed_with_cache(
                ["one", "two"],
                FakeModel([[1.0, 1.0]]),
                "openai",
                "model",
                2,
            )
        except ValueError as exc:
            assert "returned 1 vectors for 2 inputs" in str(exc)
        else:
            raise AssertionError("expected mismatch failure")

    asyncio.run(run())


def test_chunk_and_embed_writes_expected_vector_payload(monkeypatch) -> None:
    async def run() -> None:
        events = []
        checks = []
        store = FakeVectorStore()
        model = FakeModel([[0.1, 0.2], [0.3, 0.4]])

        async def get_collection(collection_name):
            return {"name": collection_name}

        def get_embedding_model(collection):
            return model

        def chunk_document(text, chunk_size, chunk_overlap, strategy):
            assert (chunk_size, chunk_overlap, strategy) == (400, 40, "paragraph")
            return [FakeChunk("first", 0, 5), FakeChunk("second", 6, 12)]

        async def get_value(key):
            assert key == "ingestion_batch_size"
            return 10

        async def ensure_job_current(job):
            checks.append(job.document_id)

        monkeypatch.setattr("bigrag.services.collection_cache.get_or_404", get_collection)
        monkeypatch.setattr(
            "bigrag.services.collection_config.get_embedding_model_for",
            get_embedding_model,
        )
        monkeypatch.setattr("bigrag.services.ingestion.chunk_document", chunk_document)
        monkeypatch.setattr("bigrag.services.runtime_settings.get_value", get_value)
        monkeypatch.setattr(queue_embedding, "embedding_cache", FakeEmbeddingCache())
        monkeypatch.setattr(
            queue_embedding,
            "truncate_to_tokens",
            lambda texts, model_name: (texts, 0),
        )

        inserted, expected = await queue_embedding.chunk_and_embed(
            _job(),
            "first second",
            "prefix",
            vector_store=store,
            emit=lambda *args, **kwargs: events.append((args, kwargs)),
            ensure_job_current=ensure_job_current,
        )

        assert (inserted, expected) == (2, 2)
        assert store.created == [("docs", 2, "tenant_id")]
        assert store.inserted[0]["ids"] == [
            "11111111-1111-1111-1111-111111111111_0",
            "11111111-1111-1111-1111-111111111111_1",
        ]
        assert store.inserted[0]["metadata"] == [
            {"char_start": 0, "char_end": 5},
            {"char_start": 6, "char_end": 12},
        ]
        assert [event[0][1] for event in events] == ["model_loaded", "chunked", "embedding"]
        assert checks == [
            "11111111-1111-1111-1111-111111111111",
            "11111111-1111-1111-1111-111111111111",
            "11111111-1111-1111-1111-111111111111",
            "11111111-1111-1111-1111-111111111111",
        ]

    asyncio.run(run())
