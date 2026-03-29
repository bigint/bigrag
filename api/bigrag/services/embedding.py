from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("bigrag.embedding")


class EmbeddingModel(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def provider(self) -> str:
        ...


class SentenceTransformerEmbedding(EmbeddingModel):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info(f"Loaded sentence-transformers model: {model_name} (dim={self._dimension})")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "sentence-transformers"


class OpenAIEmbedding(EmbeddingModel):
    def __init__(
        self, model_name: str = "text-embedding-3-small", api_key: str | None = None,
        dimension: int = 1536,
    ) -> None:
        import openai

        self._model_name = model_name
        self._dimension = dimension
        self._client = openai.AsyncOpenAI(api_key=api_key)
        logger.info(f"Initialized OpenAI embedding: {model_name} (dim={dimension})")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(input=texts, model=self._model_name)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "openai"


class OllamaEmbedding(EmbeddingModel):
    def __init__(
        self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434",
        dimension: int = 768,
    ) -> None:
        import httpx

        self._model_name = model_name
        self._dimension = dimension
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)
        logger.info(f"Initialized Ollama embedding: {model_name} (dim={dimension})")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            resp = await self._client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model_name, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            results.append(data["embeddings"][0])
        return results

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "ollama"


class CustomEmbedding(EmbeddingModel):
    """OpenAI-compatible API embedding endpoint."""

    def __init__(
        self, model_name: str, base_url: str, api_key: str | None = None,
        dimension: int = 1536,
    ) -> None:
        import openai

        self._model_name = model_name
        self._dimension = dimension
        self._client = openai.AsyncOpenAI(api_key=api_key or "unused", base_url=base_url)
        logger.info(f"Initialized custom embedding: {model_name} @ {base_url} (dim={dimension})")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(input=texts, model=self._model_name)
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "custom"


# Model registry
_models: dict[str, EmbeddingModel] = {}


def get_embedding_model(
    provider: str,
    model_name: str,
    dimension: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EmbeddingModel:
    cache_key = f"{provider}:{model_name}"
    if cache_key in _models:
        return _models[cache_key]

    if provider == "sentence-transformers":
        model = SentenceTransformerEmbedding(model_name)
    elif provider == "openai":
        model = OpenAIEmbedding(model_name, api_key=api_key, dimension=dimension or 1536)
    elif provider == "ollama":
        model = OllamaEmbedding(
            model_name,
            base_url=base_url or "http://localhost:11434",
            dimension=dimension or 768,
        )
    elif provider == "custom":
        if not base_url:
            raise ValueError("base_url required for custom embedding provider")
        model = CustomEmbedding(
            model_name, base_url=base_url, api_key=api_key, dimension=dimension or 1536
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")

    _models[cache_key] = model
    return model


AVAILABLE_MODELS = [
    {
        "provider": "sentence-transformers",
        "model": "all-MiniLM-L6-v2",
        "dimension": 384,
        "description": "Fast, lightweight English model (default)",
    },
    {
        "provider": "sentence-transformers",
        "model": "all-mpnet-base-v2",
        "dimension": 768,
        "description": "Higher quality English model",
    },
    {
        "provider": "sentence-transformers",
        "model": "multilingual-e5-large",
        "dimension": 1024,
        "description": "Multilingual model supporting 100+ languages",
    },
    {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "dimension": 1536,
        "description": "OpenAI small embedding model (requires API key)",
    },
    {
        "provider": "openai",
        "model": "text-embedding-3-large",
        "dimension": 3072,
        "description": "OpenAI large embedding model (requires API key)",
    },
    {
        "provider": "ollama",
        "model": "nomic-embed-text",
        "dimension": 768,
        "description": "Local Ollama model (requires Ollama running)",
    },
    {
        "provider": "ollama",
        "model": "mxbai-embed-large",
        "dimension": 1024,
        "description": "Local Ollama large model (requires Ollama running)",
    },
]
