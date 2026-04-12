from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa

from bigrag.config import settings
from bigrag.db.engine import session_factory
from bigrag.db.models import Collection
from bigrag.exceptions import NotFoundError, ValidationError
from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.collection_cache")


async def invalidate(name: str | None = None) -> None:
    if name:
        await redis_cache.delete(f"collection:{name}")
    else:
        await redis_cache.delete_pattern("collection:*")


def _serialize(c: Collection) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "embedding_provider": c.embedding_provider,
        "embedding_model": c.embedding_model,
        "embedding_api_key": c.embedding_api_key,
        "embedding_base_url": c.embedding_base_url,
        "dimension": c.dimension,
        "chunk_size": c.chunk_size,
        "chunk_overlap": c.chunk_overlap,
        "chunk_strategy": c.chunk_strategy,
        "document_count": c.document_count,
        "default_top_k": c.default_top_k,
        "default_min_score": c.default_min_score,
        "default_search_mode": c.default_search_mode,
        "reranking_enabled": c.reranking_enabled,
        "reranking_model": c.reranking_model,
        "reranking_api_key": c.reranking_api_key,
        "index_type": c.index_type,
        "tenant_field": c.tenant_field,
        "metadata_schema": c.metadata_schema,
        "redact_pii": c.redact_pii,
        "moderation_enabled": c.moderation_enabled,
        "metadata": c.meta or {},
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


async def get_or_404(name: str) -> dict:
    cached = await redis_cache.get(f"collection:{name}")
    if cached:
        if "id" in cached and isinstance(cached["id"], str):
            cached["id"] = uuid.UUID(cached["id"])
        return cached

    async with session_factory()() as session:
        collection = await session.scalar(
            sa.select(Collection).where(Collection.name == name)
        )
    if collection is None:
        raise NotFoundError("Collection", name)
    data = _serialize(collection)
    cacheable = {
        k: str(v) if hasattr(v, "hex") else v.isoformat() if isinstance(v, datetime) else v
        for k, v in data.items()
    }
    await redis_cache.set(
        f"collection:{name}", cacheable, ttl=settings.collection_cache_ttl,
    )
    return data


def get_embedding_model_for(collection: dict):
    """Load the embedding model for a collection, using its API key or the global fallback."""
    from bigrag.services.embedding import get_embedding_model

    api_key = collection.get("embedding_api_key") or settings.embedding_api_key
    provider = collection["embedding_provider"]
    base_url = collection.get("embedding_base_url")
    # openai_compatible often points at a self-hosted endpoint (Ollama,
    # vLLM, TEI) that doesn't check the key — only require one for the
    # hosted providers.
    if not api_key and provider in ("openai", "cohere"):
        raise ValidationError(
            f"Collection '{collection['name']}' uses "
            f"'{provider}' embeddings but no API key is configured. "
            "Set BIGRAG_EMBEDDING_API_KEY or recreate the collection with an API key."
        )

    return get_embedding_model(
        provider=provider,
        model_name=collection["embedding_model"],
        dimension=collection["dimension"],
        api_key=api_key,
        base_url=base_url,
    )


def get_reranking_config(collection: dict) -> dict:
    """Build reranking config dict from a collection row."""
    return {
        "enabled": collection.get("reranking_enabled", False),
        "model": collection.get("reranking_model", "rerank-v3.5"),
        "api_key": collection.get("reranking_api_key") or settings.embedding_api_key,
    }
