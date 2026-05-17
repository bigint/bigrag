from __future__ import annotations

import hashlib
from collections import OrderedDict

from bigrag.services.embedding.base import EmbeddingModel, logger
from bigrag.services.embedding.cohere import CohereEmbedding
from bigrag.services.embedding.openai import OpenAIEmbedding
from bigrag.services.embedding.voyage import VoyageEmbedding
from bigrag.services.url_security import normalize_url_root

_MODELS_MAX = 32
_models: OrderedDict[str, EmbeddingModel] = OrderedDict()


async def close_embedding_models() -> None:
    models = list(_models.values())
    _models.clear()
    for model in models:
        aclose = getattr(model, "aclose", None)
        if aclose is None:
            continue
        try:
            await aclose()
        except Exception as exc:
            logger.warning("failed to close embedding model", error=repr(exc))


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
