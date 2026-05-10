from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bigrag.exceptions import ValidationError
from bigrag.services import retrieval
from bigrag.services.vector_store import VectorStoreFeatureError


class FakeEmbeddingModel:
    provider = "openai"
    name = "model"
    dimension = 2
    cache_identity = "identity"

    def __init__(self) -> None:
        self.calls = []

    async def embed(self, texts, *, input_type="document"):
        self.calls.append((texts, input_type))
        return [[0.1, 0.2] for _ in texts]


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.increments = []

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        self.increments.append(key)
        self.values[key] = int(self.values.get(key, 0)) + 1


class FakeVectorStore:
    provider = "fake"

    def __init__(self, *, supports_text_search=True) -> None:
        self.supports_text_search = supports_text_search
        self.search_calls = []
        self.text_search_calls = []

    async def search(self, **kwargs):
        self.search_calls.append(kwargs)
        return [
            {"id": "semantic", "text": "semantic result", "score": 0.8},
            {"id": "shared", "text": "shared result", "score": 0.5},
        ]

    async def text_search(self, **kwargs):
        self.text_search_calls.append(kwargs)
        return [
            {"id": "keyword", "text": "hello world"},
            {"id": "shared", "text": "hello semantic"},
            {"id": "miss", "text": "unrelated"},
        ]


def configure_retrieval(monkeypatch, *, cache_ttl=0, store=None, cached=None):
    redis = FakeRedis()
    cache = dict(cached or {})
    writes = []

    async def get_value(key):
        if key == "query_embedding_cache_ttl":
            return cache_ttl
        if key == "query_result_cache_ttl":
            return cache_ttl
        return 0

    async def get_values(keys):
        return {key: await get_value(key) for key in keys}

    async def cache_get(key):
        return cache.get(key)

    async def cache_set(key, value, ttl):
        writes.append((key, value, ttl))
        cache[key] = value

    monkeypatch.setattr(retrieval.redis_cache, "get_redis", lambda: redis)
    monkeypatch.setattr(retrieval.redis_cache, "get", cache_get)
    monkeypatch.setattr(retrieval.redis_cache, "set", cache_set)
    monkeypatch.setattr(retrieval, "get_value", get_value)
    monkeypatch.setattr(retrieval, "get_values", get_values)
    monkeypatch.setattr(retrieval, "safe_create_task", lambda coro, name=None: coro.close())
    monkeypatch.setattr(retrieval, "vector_store", store or FakeVectorStore())
    return SimpleNamespace(redis=redis, cache=cache, writes=writes)


def test_retrieval_helpers_and_query_cache(monkeypatch) -> None:
    async def run() -> None:
        context = configure_retrieval(monkeypatch, cache_ttl=30)
        model = FakeEmbeddingModel()

        assert retrieval._tokenize_query(" A bb ccc ") == ["bb", "ccc"]
        assert retrieval._keyword_score("hello world", ["hello", "missing"]) == 0.5
        assert (
            retrieval.fuse_results(
                [
                    [{"id": "a", "score": 0.2}, {"id": "b", "score": 0.1}],
                    [{"id": "b", "score": 0.9}],
                ]
            )[0]["id"]
            == "b"
        )

        await retrieval.invalidate_collection_query_cache("docs")
        assert context.redis.increments == ["bigrag:query_epoch:docs"]

        vector = await retrieval._embed_query_with_cache("hello", model)
        assert vector == [0.1, 0.2]
        assert model.calls == [(["hello"], "query")]
        assert context.writes[0][2] == 30
        assert await retrieval._embed_query_with_cache("hello", model) == [0.1, 0.2]
        assert model.calls == [(["hello"], "query")]

        key = await retrieval._query_result_cache_key(
            collection_name="docs",
            query="hello",
            embedding_model=model,
            top_k=3,
            filters={"tenant": "a"},
            min_score=0.2,
            search_mode="semantic",
            reranking_config={"enabled": True, "model": "rerank"},
            rerank_override=False,
        )
        await retrieval._store_query_result(
            key,
            retrieval.RetrievalOutcome(results=[{"id": "a"}], total_ms=1.2),
        )
        cached = await retrieval._cached_query_result(key)
        assert cached is not None
        assert cached.results == [{"id": "a"}]

    asyncio.run(run())


def test_retrieve_semantic_keyword_hybrid_and_cached(monkeypatch) -> None:
    async def run() -> None:
        store = FakeVectorStore()
        configure_retrieval(monkeypatch, store=store)
        model = FakeEmbeddingModel()

        semantic = await retrieval.retrieve("docs", "hello world", model, top_k=1)
        assert semantic.results == [{"id": "semantic", "text": "semantic result", "score": 0.8}]
        assert store.search_calls[0]["query_embedding"] == [0.1, 0.2]

        keyword = await retrieval.retrieve(
            "docs",
            "hello world",
            model,
            top_k=2,
            search_mode="keyword",
        )
        assert [item["id"] for item in keyword.results] == ["keyword", "shared"]
        assert keyword.results[0]["score"] == 1.0

        hybrid = await retrieval.retrieve(
            "docs",
            "hello world",
            model,
            top_k=3,
            min_score=0.01,
            search_mode="hybrid",
        )
        assert [item["id"] for item in hybrid.results] == ["shared", "semantic", "keyword"]

        cached_context = configure_retrieval(
            monkeypatch,
            cache_ttl=30,
            cached={"fixed": {"results": [{"id": "cached", "score": 1.0}]}},
        )

        async def fixed_cache_key(**kwargs):
            return "fixed"

        monkeypatch.setattr(retrieval, "_query_result_cache_key", fixed_cache_key)
        cached = await retrieval.retrieve("docs", "hello", model)
        assert cached.results == [{"id": "cached", "score": 1.0}]
        assert cached_context.writes == []

    asyncio.run(run())


def test_retrieve_validation_errors_and_reranking(monkeypatch) -> None:
    async def run() -> None:
        configure_retrieval(monkeypatch, store=FakeVectorStore(supports_text_search=False))
        with pytest.raises(ValidationError):
            await retrieval.retrieve(
                "docs",
                "hello",
                FakeEmbeddingModel(),
                search_mode="keyword",
            )

        class FailingStore(FakeVectorStore):
            async def text_search(self, **kwargs):
                raise VectorStoreFeatureError("no text")

        configure_retrieval(monkeypatch, store=FailingStore())
        with pytest.raises(ValidationError):
            await retrieval.retrieve(
                "docs",
                "hello",
                FakeEmbeddingModel(),
                search_mode="keyword",
            )

        configure_retrieval(monkeypatch, store=FakeVectorStore())
        monkeypatch.setattr(
            retrieval,
            "rerank_results",
            lambda results, query, model, api_key: asyncio.sleep(
                0,
                result=[dict(results[-1], score=0.99), dict(results[0], score=0.5)],
            ),
        )
        reranked = await retrieval.retrieve(
            "docs",
            "hello",
            FakeEmbeddingModel(),
            top_k=2,
            reranking_config={"enabled": True, "model": "rerank", "api_key": "key"},
        )
        assert [item["id"] for item in reranked.results] == ["shared", "semantic"]

    asyncio.run(run())


def test_rerank_results_uses_cohere_and_handles_failures(monkeypatch) -> None:
    async def run() -> None:
        class FakeClient:
            def __init__(self, api_key=None) -> None:
                self.closed = False

            async def rerank(self, **kwargs):
                return SimpleNamespace(
                    results=[
                        SimpleNamespace(index=1, relevance_score=0.91),
                        SimpleNamespace(index=0, relevance_score=0.42),
                    ]
                )

            async def close(self):
                self.closed = True

        monkeypatch.setitem(
            __import__("sys").modules,
            "cohere",
            SimpleNamespace(AsyncClient=FakeClient),
        )
        results = [{"id": "a", "text": "first"}, {"id": "b", "text": "second"}]

        reranked = await retrieval.rerank_results(results, "query", api_key="key")

        assert reranked == [
            {"id": "b", "text": "second", "score": 0.91},
            {"id": "a", "text": "first", "score": 0.42},
        ]

        class FailingClient(FakeClient):
            async def rerank(self, **kwargs):
                raise RuntimeError("failed")

        monkeypatch.setitem(
            __import__("sys").modules,
            "cohere",
            SimpleNamespace(AsyncClient=FailingClient),
        )
        assert await retrieval.rerank_results(results, "query") is results
        assert await retrieval.rerank_results([], "query") == []

    asyncio.run(run())


def test_retrieve_multi_merges_collection_results(monkeypatch) -> None:
    async def run() -> None:
        async def fake_retrieve(collection_name, **kwargs):
            return retrieval.RetrievalOutcome(
                results=[{"id": collection_name, "score": 0.9 if collection_name == "a" else 0.8}]
            )

        monkeypatch.setattr(retrieval, "retrieve", fake_retrieve)

        results = await retrieval.retrieve_multi(
            ["b", "a"],
            "query",
            {"a": FakeEmbeddingModel(), "b": FakeEmbeddingModel()},
            top_k=2,
            reranking_configs={"a": {"enabled": True}},
        )

        assert results == [
            {"id": "a", "score": 0.9, "collection": "a"},
            {"id": "b", "score": 0.8, "collection": "b"},
        ]

    asyncio.run(run())
