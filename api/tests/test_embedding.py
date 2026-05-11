from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from rag_computer.services import embedding


class FakeSemaphore:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_truncate_to_tokens_uses_fallback_when_tokenizer_fails(monkeypatch) -> None:
    def fail_import(name):
        if name == "tiktoken":
            raise RuntimeError("no tokenizer")
        return __import__(name)

    monkeypatch.setattr("builtins.__import__", fail_import)

    texts, warnings = embedding.truncate_to_tokens(["abcd", "abcdef"], None, max_tokens=1)

    assert texts == ["abcd", "abcd"]
    assert warnings == [False, True]


def test_embedding_model_cache_and_provider_validation(monkeypatch) -> None:
    class FakeOpenAIEmbedding:
        def __init__(self, model_name, api_key=None, dimension=1536, base_url=None) -> None:
            self.model_name = model_name
            self.api_key = api_key
            self.dimension = dimension
            self.base_url = base_url

    monkeypatch.setattr(embedding, "OpenAIEmbedding", FakeOpenAIEmbedding)
    monkeypatch.setattr(embedding, "normalize_url_root", lambda value: value.rstrip("/"))
    embedding._models.clear()

    first = embedding.get_embedding_model(
        "openai",
        "model",
        dimension=8,
        api_key="secret",
        base_url="https://example.com/",
    )
    second = embedding.get_embedding_model(
        "openai",
        "model",
        dimension=8,
        api_key="secret",
        base_url="https://example.com",
    )

    assert first is second
    assert first.dimension == 8
    with pytest.raises(ValueError):
        embedding.get_embedding_model("openai_compatible", "model")
    with pytest.raises(ValueError):
        embedding.get_embedding_model("unknown", "model")


def test_model_cache_evicts_oldest(monkeypatch) -> None:
    class FakeOpenAIEmbedding:
        def __init__(self, model_name, api_key=None, dimension=1536, base_url=None) -> None:
            self.model_name = model_name

    monkeypatch.setattr(embedding, "OpenAIEmbedding", FakeOpenAIEmbedding)
    embedding._models.clear()

    for index in range(embedding._MODELS_MAX + 1):
        embedding.get_embedding_model("openai", f"model-{index}")

    assert len(embedding._models) == embedding._MODELS_MAX
    assert "openai:model-0:none:def" not in embedding._models


def test_openai_embedding_embed_and_properties(monkeypatch) -> None:
    async def run() -> None:
        class FakeEmbeddings:
            async def create(self, input, model):
                assert input == ["hello"]
                assert model == "text-embedding-3-small"
                return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])])

        class FakeAsyncOpenAI:
            def __init__(self, api_key=None, base_url=None) -> None:
                self.embeddings = FakeEmbeddings()

        monkeypatch.setitem(
            __import__("sys").modules,
            "openai",
            SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI),
        )
        monkeypatch.setattr(embedding, "_get_semaphore", lambda key: FakeSemaphore())
        monkeypatch.setattr(embedding, "validate_embedding_base_url_sync", lambda value: value)

        model = embedding.OpenAIEmbedding(api_key="key", dimension=2)

        assert await model.embed(["hello"], input_type="query") == [[0.1, 0.2]]
        assert model.dimension == 2
        assert model.name == "text-embedding-3-small"
        assert model.provider == "openai"
        assert model.cache_identity.startswith("openai:text-embedding-3-small:2:")

    asyncio.run(run())


def test_cohere_embedding_maps_input_type(monkeypatch) -> None:
    async def run() -> None:
        calls = []

        class FakeClient:
            def __init__(self, api_key=None) -> None:
                self.api_key = api_key

            async def embed(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(embeddings=SimpleNamespace(float_=[[1.0, 2.0]]))

        monkeypatch.setitem(
            __import__("sys").modules,
            "cohere",
            SimpleNamespace(AsyncClient=FakeClient),
        )
        monkeypatch.setattr(embedding, "_get_semaphore", lambda key: FakeSemaphore())

        model = embedding.CohereEmbedding(api_key="key", dimension=2)

        assert await model.embed(["hello"], input_type="query") == [[1.0, 2.0]]
        assert calls[0]["input_type"] == "search_query"
        assert model.provider == "cohere"
        assert model.cache_identity == "cohere:embed-english-v3.0:2"

    asyncio.run(run())


def test_voyage_embedding_request_success_and_error(monkeypatch) -> None:
    async def run() -> None:
        class FakeResponse:
            def __init__(self, status_code=200) -> None:
                self.status_code = status_code
                self.text = "bad"

            def json(self):
                return {"data": [{"embedding": [0.3, 0.4]}]}

        class FakeAsyncClient:
            def __init__(self, timeout) -> None:
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json, headers):
                assert json["input_type"] == "document"
                assert headers["Authorization"] == "Bearer key"
                return FakeResponse(500 if json["input"] == ["fail"] else 200)

        monkeypatch.setitem(
            __import__("sys").modules,
            "httpx",
            SimpleNamespace(AsyncClient=FakeAsyncClient),
        )
        monkeypatch.setattr(embedding, "_get_semaphore", lambda key: FakeSemaphore())

        model = embedding.VoyageEmbedding(api_key="key", dimension=2)

        assert await model.embed(["ok"], input_type="unknown") == [[0.3, 0.4]]
        with pytest.raises(RuntimeError):
            await model.embed(["fail"])
        with pytest.raises(ValueError):
            embedding.VoyageEmbedding(api_key=None)

    asyncio.run(run())
