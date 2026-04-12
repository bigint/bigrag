from __future__ import annotations

import asyncio
import hashlib
from abc import ABC, abstractmethod

from bigrag.logging import get_logger

logger = get_logger("bigrag.embedding")

_embed_semaphore: asyncio.Semaphore | None = None

# Approximate token limits per model. We use tiktoken when available for
# OpenAI, otherwise fall back to a 4-chars-per-token heuristic. Numbers
# intentionally a bit below the provider's published maximum to give a
# safety margin for provider-side tokenizer drift.
_TOKEN_LIMITS: dict[str, int] = {
    "text-embedding-3-small": 8000,
    "text-embedding-3-large": 8000,
    "text-embedding-ada-002": 8000,
    "embed-english-v3.0": 500,
    "embed-multilingual-v3.0": 500,
    "embed-english-light-v3.0": 500,
    "embed-multilingual-light-v3.0": 500,
}


def _get_semaphore() -> asyncio.Semaphore:
    global _embed_semaphore
    if _embed_semaphore is None:
        from bigrag.config import settings

        _embed_semaphore = asyncio.Semaphore(settings.embedding_concurrency)
    return _embed_semaphore


def count_tokens(text: str, model: str | None = None) -> int:
    """Best-effort token count. Prefer tiktoken when available for
    OpenAI-compatible models; otherwise fall back to a char-based
    heuristic."""
    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding(
                "cl100k_base"
            )
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:  # noqa: BLE001 — tiktoken missing or model unknown
        # ~4 characters per token is a safe over-estimate for English.
        return max(1, len(text) // 4)


def truncate_to_tokens(
    texts: list[str],
    model: str | None,
    max_tokens: int | None = None,
) -> tuple[list[str], list[bool]]:
    """Truncate each text to the model's token cap. Returns (truncated,
    warnings) — warnings[i] is True if texts[i] was trimmed.

    Falls back to character truncation when tiktoken isn't installed."""
    limit = max_tokens
    if limit is None and model:
        limit = _TOKEN_LIMITS.get(model)
    if limit is None:
        limit = 8000  # conservative

    try:
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding(
                "cl100k_base"
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
    except Exception:  # noqa: BLE001
        # Char-based fallback: 4 chars ≈ 1 token.
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


class OpenAIEmbedding(EmbeddingModel):
    """Works against OpenAI directly or any OpenAI-compatible endpoint
    (Azure OpenAI, vLLM, Ollama's /v1/embeddings, Infinity, LiteLLM's
    proxy, Bedrock via LiteLLM, Vertex via adaptor, etc.) — pass
    ``base_url`` at construction time."""

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
                "Install it with: pip install 'bigrag[openai]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._base_url = base_url
        self._client = openai.AsyncOpenAI(
            api_key=api_key or "not-required",
            base_url=base_url,
        )
        logger.info(
            f"Initialized OpenAI-compatible embedding: {model_name} "
            f"(dim={dimension}, base_url={base_url or 'default'})"
        )

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                f"openai_embed: {truncated}/{len(texts)} inputs exceeded token "
                f"limit and were truncated (model={self._model_name})"
            )
        async with _get_semaphore():
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
                "Install it with: pip install 'bigrag[cohere]'"
            ) from e

        self._model_name = model_name
        self._dimension = dimension
        self._client = cohere.AsyncClient(api_key=api_key)
        logger.info(f"Initialized Cohere embedding: {model_name} (dim={dimension})")

    async def embed(self, texts: list[str], *, input_type: str = "document") -> list[list[float]]:
        texts, warnings = truncate_to_tokens(texts, self._model_name)
        if any(warnings):
            truncated = sum(1 for w in warnings if w)
            logger.warning(
                f"cohere_embed: {truncated}/{len(texts)} inputs exceeded token "
                f"limit and were truncated (model={self._model_name})"
            )
        cohere_input_type = self._INPUT_TYPE_MAP.get(input_type, "search_document")
        async with _get_semaphore():
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


_models: dict[str, EmbeddingModel] = {}


def get_embedding_model(
    provider: str,
    model_name: str,
    dimension: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> EmbeddingModel:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:8] if api_key else "none"
    base_tag = hashlib.sha256((base_url or "").encode()).hexdigest()[:6] if base_url else "def"
    cache_key = f"{provider}:{model_name}:{key_hash}:{base_tag}"
    if cache_key in _models:
        return _models[cache_key]

    if provider in ("openai", "openai_compatible"):
        model = OpenAIEmbedding(
            model_name,
            api_key=api_key,
            dimension=dimension or 1536,
            base_url=base_url,
        )
    elif provider == "cohere":
        model = CohereEmbedding(model_name, api_key=api_key, dimension=dimension or 1024)
    else:
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Supported: openai, openai_compatible, cohere"
        )

    _models[cache_key] = model
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
