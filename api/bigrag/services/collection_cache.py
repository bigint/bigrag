from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from bigrag.config import settings
from bigrag.database import db
from bigrag.services.crypto import decrypt

logger = logging.getLogger("bigrag.collection_cache")

_cache: dict[str, tuple[dict, float]] = {}


def invalidate(name: str | None = None) -> None:
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()


async def get_or_404(name: str) -> dict:
    entry = _cache.get(name)
    if entry:
        data, expires_at = entry
        if time.monotonic() < expires_at:
            return data
        _cache.pop(name, None)

    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    data = dict(row)
    if data.get("embedding_api_key"):
        try:
            data["embedding_api_key"] = decrypt(data["embedding_api_key"])
        except Exception as e:
            logger.error(f"Failed to decrypt API key for collection '{name}': {e}")
            data["embedding_api_key"] = None

    _cache[name] = (data, time.monotonic() + settings.collection_cache_ttl)
    return data


def get_embedding_model_for(collection: dict):
    """Load the embedding model for a collection, using its API key or the global fallback."""
    from bigrag.services.embedding import get_embedding_model

    api_key = collection.get("embedding_api_key") or settings.embedding_api_key
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Collection '{collection['name']}' uses '{collection['embedding_provider']}' embeddings "
                   f"but no API key is configured. Set BIGRAG_EMBEDDING_API_KEY or recreate the collection with an API key.",
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
