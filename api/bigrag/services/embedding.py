from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("bigrag.embedding")

_embed_semaphore = asyncio.Semaphore(8)


class EmbeddingModel(ABC):
    @abstractmethod
    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...


class OpenAIEmbedding(EmbeddingModel):
    def __init__(
        self, model_name: str = "text-embedding-3-small", api_key: str | None = None,
        dimension: int = 1536,
    ) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAI embeddings. "
                "Install it with: pip install 'bigrag[openai]'"
            )

        self._model_name = model_name
        self._dimension = dimension
        self._client = openai.AsyncOpenAI(api_key=api_key)
        logger.info(f"Initialized OpenAI embedding: {model_name} (dim={dimension})")

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        async with _embed_semaphore:
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


class CohereEmbedding(EmbeddingModel):
    _INPUT_TYPE_MAP = {
        "document": "search_document",
        "query": "search_query",
    }

    def __init__(
        self, model_name: str = "embed-english-v3.0", api_key: str | None = None,
        dimension: int = 1024,
    ) -> None:
        try:
            import cohere
        except ImportError:
            raise ImportError(
                "cohere package is required for Cohere embeddings. "
                "Install it with: pip install 'bigrag[cohere]'"
            )

        self._model_name = model_name
        self._dimension = dimension
        self._client = cohere.AsyncClient(api_key=api_key)
        logger.info(f"Initialized Cohere embedding: {model_name} (dim={dimension})")

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        cohere_input_type = self._INPUT_TYPE_MAP.get(input_type, "search_document")
        async with _embed_semaphore:
            response = await self._client.embed(
                texts=texts,
                model=self._model_name,
                input_type=cohere_input_type,
                embedding_types=["float"],
            )
        return [list(e) for e in response.embeddings.float_]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "cohere"


_models: dict[str, EmbeddingModel] = {}


def get_embedding_model(
    provider: str,
    model_name: str,
    dimension: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EmbeddingModel:
    import hashlib

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8] if api_key else "none"
    cache_key = f"{provider}:{model_name}:{key_hash}"
    if cache_key in _models:
        return _models[cache_key]

    if provider == "openai":
        model = OpenAIEmbedding(model_name, api_key=api_key, dimension=dimension or 1536)
    elif provider == "cohere":
        model = CohereEmbedding(model_name, api_key=api_key, dimension=dimension or 1024)
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider}. Supported providers: openai, cohere"
        )

    _models[cache_key] = model
    return model


AVAILABLE_MODELS = [
    {"provider": "openai", "model": "text-embedding-3-small", "dimension": 1536, "description": "OpenAI small embedding model"},
    {"provider": "openai", "model": "text-embedding-3-large", "dimension": 3072, "description": "OpenAI large embedding model"},
    {"provider": "cohere", "model": "embed-english-v3.0", "dimension": 1024, "description": "Cohere English embedding model"},
    {"provider": "cohere", "model": "embed-multilingual-v3.0", "dimension": 1024, "description": "Cohere multilingual model (100+ languages)"},
    {"provider": "cohere", "model": "embed-english-light-v3.0", "dimension": 384, "description": "Cohere lightweight English model"},
    {"provider": "cohere", "model": "embed-multilingual-light-v3.0", "dimension": 384, "description": "Cohere lightweight multilingual model"},
]
