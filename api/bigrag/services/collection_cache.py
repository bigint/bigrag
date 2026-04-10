from __future__ import annotations

import uuid
from datetime import datetime

from bigrag.config import settings
from bigrag.database import db
from bigrag.exceptions import NotFoundError, ValidationError
from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.collection_cache")


async def invalidate(name: str | None = None) -> None:
    if name:
        await redis_cache.delete(f"collection:{name}")
    else:
        await redis_cache.delete_pattern("collection:*")


async def get_or_404(name: str) -> dict:
    cached = await redis_cache.get(f"collection:{name}")
    if cached:
        if "id" in cached and isinstance(cached["id"], str):
            cached["id"] = uuid.UUID(cached["id"])
        return cached

    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise NotFoundError("Collection", name)
    data = {
        k: str(v) if hasattr(v, "hex") else v.isoformat() if isinstance(v, datetime) else v
        for k, v in dict(row).items()
    }
    await redis_cache.set(
        f"collection:{name}", data, ttl=settings.collection_cache_ttl,
    )
    return data


def get_embedding_model_for(collection: dict):
    """Load the embedding model for a collection, using its API key or the global fallback."""
    from bigrag.services.embedding import get_embedding_model

    api_key = collection.get("embedding_api_key") or settings.embedding_api_key
    if not api_key:
        raise ValidationError(
            f"Collection '{collection['name']}' uses "
            f"'{collection['embedding_provider']}' embeddings but no API key is configured. "
            "Set BIGRAG_EMBEDDING_API_KEY or recreate the collection with an API key."
        )

    return get_embedding_model(
        provider=collection["embedding_provider"],
        model_name=collection["embedding_model"],
        dimension=collection["dimension"],
        api_key=api_key,
    )


def get_reranking_config(collection: dict) -> dict:
    """Build reranking config dict from a collection row."""
    return {
        "enabled": collection.get("reranking_enabled", False),
        "model": collection.get("reranking_model", "rerank-v3.5"),
        "api_key": collection.get("reranking_api_key") or settings.embedding_api_key,
    }
