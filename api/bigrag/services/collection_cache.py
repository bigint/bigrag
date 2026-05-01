from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.config import settings
from bigrag.db.engine import session_factory
from bigrag.db.models import Collection
from bigrag.exceptions import NotFoundError
from bigrag.services import redis_cache


def _cache_key(name: str) -> str:
    return f"collection:{name}"


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
        "metadata": c.meta or {},
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _deserialize(data: dict) -> dict:
    out = dict(data)
    if isinstance(out.get("id"), str):
        out["id"] = uuid.UUID(out["id"])
    return out


async def get_or_404(name: str) -> dict:
    cached = await redis_cache.get(_cache_key(name))
    if isinstance(cached, dict):
        return _deserialize(cached)

    async with session_factory()() as session:
        collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
        if collection is None:
            raise NotFoundError("Collection", name)
        serialized = _serialize(collection)
        ttl = settings.collection_cache_ttl
        if ttl > 0:
            await redis_cache.set(_cache_key(name), serialized, ttl=ttl)
        return serialized


async def invalidate(name: str) -> None:
    await redis_cache.delete(_cache_key(name))
