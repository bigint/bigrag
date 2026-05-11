from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod
from collections import OrderedDict

from rag_computer.logging import get_logger
from rag_computer.services.url_security import (
    normalize_url_root,
    validate_embedding_base_url_sync,
)

logger = get_logger("rag_computer.embedding")

_embed_semaphores: dict[str, asyncio.Semaphore] = {}

_TOKEN_LIMITS: dict[str, int] = {
    "text-embedding-3-small": 8000,
    "text-embedding-3-large": 8000,
    "text-embedding-ada-002": 8000,
    "embed-english-v3.0": 500,
    "embed-multilingual-v3.0": 500,
    "embed-english-light-v3.0": 500,
    "embed-multilingual-light-v3.0": 500,
    "voyage-3-large": 32000,
    "voyage-3.5": 32000,
    "voyage-3.5-lite": 32000,
    "voyage-code-3": 32000,
    "voyage-finance-2": 32000,
    "voyage-law-2": 16000,
}


def _get_semaphore(key: str) -> asyncio.Semaphore:
    if key not in _embed_semaphores:
        from rag_computer.services.runtime_settings import sync_value

        _embed_semaphores[key] = asyncio.Semaphore(sync_value("embedding_concurrency"))
    return _embed_semaphores[key]


def truncate_to_tokens(
    texts: list[str],
    model: str | None,
    max_tokens: int | None = None,
) -> tuple[list[str], list[bool]]:

    limit = max_tokens
    if limit is None and model:
        limit = _TOKEN_LIMITS.get(model)
    if limit is None:
        limit = 8000

    try:
        import tiktoken

        try:
            enc = (
                tiktoken.encoding_for_model(model)
                if model
                else tiktoken.get_encoding("cl100k_base")
            )
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        out_texts: list[str] = []
        warnings: list[bool] = []
        for text in texts:
            tokens = enc.encode(text)
            if len(tokens) > limit:
                out_texts.append(enc.decode(tokens[:limit]))
                warnings.append(True)
            else:
                out_texts.append(text)
                warnings.append(False)
        return out_texts, warnings
    except Exception:
        char_limit = limit * 4
        out_texts = []
        warnings = []
        for text in texts:
            if len(text) > char_limit:
                out_texts.append(text[:char_limit])
                warnings.append(True)
            else:
                out_texts.append(text)
                warnings.append(False)
        return out_texts, warnings


class EmbeddingModel(ABC):
    @abstractmethod
    async def embed(
        self, texts: list[str], *, input_type: str = "document"
    ) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def provider(self) -> str: ...

    @property
    @abstractmethod
    def cache_identity(self) -> str: ...


class OpenAIEmbedding(EmbeddingModel):
    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimension: int = 1536,
        base_url: str | None = None,
    ) -> None:
        try:
            import openai
        except ImportError as e:
            raise ImportError(
                "openai package is required for OpenAI-compatible embeddings. "
                "Install it with: pip install 'rag-computer[openai]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._base_url = validate_embedding_base_url_sync(base_url)
        self._semaphore_key = f"openai:{self._base_url or 'default'}"
        base_tag = hashlib.sha256((self._base_url or "").encode()).hexdigest()[:12]
        self._cache_identity = f"openai:{model_name}:{dimension}:{base_tag}"
        self._client = openai.AsyncOpenAI(
            api_key=api_key or "not-required",
            base_url=self._base_url,
        )
        logger.info(
            "initialized openai-compatible embedding",
            model=model_name,
            dimension=dimension,
            base_url=self._base_url or "default",
        )

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        _ = input_type
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "openai inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        async with _get_semaphore(self._semaphore_key):
            response = await asyncio.wait_for(
                self._client.embeddings.create(input=texts, model=self._model_name),
                timeout=60,
            )
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

    @property
    def cache_identity(self) -> str:
        return self._cache_identity


class CohereEmbedding(EmbeddingModel):
    _INPUT_TYPE_MAP = {
        "document": "search_document",
        "query": "search_query",
    }

    def __init__(
        self,
        model_name: str = "embed-english-v3.0",
        api_key: str | None = None,
        dimension: int = 1024,
    ) -> None:
        try:
            import cohere
        except ImportError as e:
            raise ImportError(
                "cohere package is required for Cohere embeddings. "
                "Install it with: pip install 'rag-computer[cohere]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._semaphore_key = "cohere"
        self._cache_identity = f"cohere:{model_name}:{dimension}"
        self._client = cohere.AsyncClient(api_key=api_key)
        logger.info("initialized cohere embedding", model=model_name, dimension=dimension)

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "cohere inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        cohere_input_type = self._INPUT_TYPE_MAP.get(input_type, "search_document")
        async with _get_semaphore(self._semaphore_key):
            response = await asyncio.wait_for(
                self._client.embed(
                    texts=texts,
                    model=self._model_name,
                    input_type=cohere_input_type,
                    embedding_types=["float"],
                ),
                timeout=60,
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

    @property
    def cache_identity(self) -> str:
        return self._cache_identity


class VoyageEmbedding(EmbeddingModel):
    _API_URL = "https://api.voyageai.com/v1/embeddings"
    _INPUT_TYPES = {"document", "query"}

    def __init__(
        self,
        model_name: str = "voyage-3.5",
        api_key: str | None = None,
        dimension: int = 1024,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for the Voyage embedding provider")
        self._model_name = model_name
        self._dimension = dimension
        self._api_key = api_key
        self._semaphore_key = "voyage"
        self._cache_identity = f"voyage:{model_name}:{dimension}"
        logger.info("initialized voyage embedding", model=model_name, dimension=dimension)

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        import httpx

        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                "voyage inputs exceeded token limit and were truncated",
                truncated=truncated,
                inputs=len(texts),
                model=self._model_name,
            )
        voyage_input_type = input_type if input_type in self._INPUT_TYPES else "document"
        payload = {
            "input": texts,
            "model": self._model_name,
            "input_type": voyage_input_type,
            "output_dimension": self._dimension,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with _get_semaphore(self._semaphore_key):
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self._API_URL, json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Voyage embed failed ({response.status_code}): {response.text[:500]}"
            )
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def name(self) -> str:
        return self._model_name

    @property
    def provider(self) -> str:
        return "voyage"

    @property
    def cache_identity(self) -> str:
        return self._cache_identity


_MODELS_MAX = 32
_models: OrderedDict[str, EmbeddingModel] = OrderedDict()


def get_embedding_model(
    provider: str,
    model_name: str,
    dimension: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EmbeddingModel:
    base_url = normalize_url_root(base_url) if base_url else None
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8] if api_key else "none"
    base_tag = hashlib.sha256((base_url or "").encode()).hexdigest()[:6] if base_url else "def"
    cache_key = f"{provider}:{model_name}:{key_hash}:{base_tag}"
    if cache_key in _models:
        _models.move_to_end(cache_key)
        return _models[cache_key]

    if provider in ("openai", "openai_compatible"):
        if provider == "openai_compatible" and not base_url:
            raise ValueError("base_url is required for openai_compatible embeddings")
        model = OpenAIEmbedding(
            model_name,
            api_key=api_key,
            dimension=dimension or 1536,
            base_url=base_url,
        )
    elif provider == "cohere":
        model = CohereEmbedding(model_name, api_key=api_key, dimension=dimension or 1024)
    elif provider == "voyage":
        model = VoyageEmbedding(model_name, api_key=api_key, dimension=dimension or 1024)
    else:
        raise ValueError(
            "Unknown embedding provider: "
            f"{provider}. Supported: openai, openai_compatible, cohere, voyage"
        )

    _models[cache_key] = model
    while len(_models) > _MODELS_MAX:
        _models.popitem(last=False)
    return model


AVAILABLE_MODELS = [
    {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "dimension": 1536,
        "description": "OpenAI small embedding model",
    },
    {
        "provider": "openai",
        "model": "text-embedding-3-large",
        "dimension": 3072,
        "description": "OpenAI large embedding model",
    },
    {
        "provider": "cohere",
        "model": "embed-english-v3.0",
        "dimension": 1024,
        "description": "Cohere English embedding model",
    },
    {
        "provider": "cohere",
        "model": "embed-multilingual-v3.0",
        "dimension": 1024,
        "description": "Cohere multilingual model (100+ languages)",
    },
    {
        "provider": "cohere",
        "model": "embed-english-light-v3.0",
        "dimension": 384,
        "description": "Cohere lightweight English model",
    },
    {
        "provider": "cohere",
        "model": "embed-multilingual-light-v3.0",
        "dimension": 384,
        "description": "Cohere lightweight multilingual model",
    },
    {
        "provider": "voyage",
        "model": "voyage-3-large",
        "dimension": 1024,
        "description": "Voyage AI flagship general-purpose model",
    },
    {
        "provider": "voyage",
        "model": "voyage-3.5",
        "dimension": 1024,
        "description": "Voyage AI default general-purpose model",
    },
    {
        "provider": "voyage",
        "model": "voyage-3.5-lite",
        "dimension": 1024,
        "description": "Voyage AI cheap general-purpose model",
    },
    {
        "provider": "voyage",
        "model": "voyage-code-3",
        "dimension": 1024,
        "description": "Voyage AI code-tuned model",
    },
    {
        "provider": "voyage",
        "model": "voyage-finance-2",
        "dimension": 1024,
        "description": "Voyage AI finance-domain model",
    },
    {
        "provider": "voyage",
        "model": "voyage-law-2",
        "dimension": 1024,
        "description": "Voyage AI legal-domain model",
    },
    {
        "provider": "openai_compatible",
        "model": "(custom)",
        "dimension": 1024,
        "description": (
            "Any OpenAI-compatible endpoint. Set embedding_base_url to point at "
            "Ollama, vLLM, TEI, Infinity, LiteLLM, or Azure OpenAI — provide the "
            "target model name and dimension via the collection config."
        ),
    },
]
