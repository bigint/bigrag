from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa

from rag_computer.db.engine import session_factory
from rag_computer.db.models import Collection, EmbeddingPreset
from rag_computer.exceptions import NotFoundError
from rag_computer.services import redis_cache
from rag_computer.services.runtime_settings import get_value


def _cache_key(name: str) -> str:
    return f"collection:{name}"


def _serialize(c: Collection, preset: EmbeddingPreset | None = None) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "embedding_provider": c.embedding_provider,
        "embedding_model": c.embedding_model,
        "embedding_api_key": c.embedding_api_key,
        "embedding_base_url": c.embedding_base_url,
        "embedding_preset_id": str(c.embedding_preset_id) if c.embedding_preset_id else None,
        "embedding_preset_api_key": preset.api_key if preset else None,
        "embedding_preset_base_url": preset.base_url if preset else None,
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
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _deserialize(data: dict) -> dict:
    out = dict(data)
    if isinstance(out.get("id"), str):
        out["id"] = uuid.UUID(out["id"])
    for key in ("created_at", "updated_at"):
        if isinstance(out.get(key), str):
            out[key] = datetime.fromisoformat(out[key])
    return out


async def get_or_404(name: str) -> dict:
    cached = await redis_cache.get(_cache_key(name))
    if isinstance(cached, dict):
        return _deserialize(cached)

    async with session_factory()() as session:
        collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
        if collection is None:
            raise NotFoundError("Collection", name)
        preset: EmbeddingPreset | None = None
        if collection.embedding_preset_id is not None:
            preset = await session.get(EmbeddingPreset, collection.embedding_preset_id)
        serialized = _serialize(collection, preset)
        ttl = await get_value("collection_cache_ttl")
        if ttl > 0:
            await redis_cache.set(_cache_key(name), serialized, ttl=ttl)
        return serialized


async def invalidate(name: str) -> None:
    await redis_cache.delete(_cache_key(name))


async def invalidate_for_preset(preset_id: uuid.UUID) -> None:
    async with session_factory()() as session:
        names = (
            await session.scalars(
                sa.select(Collection.name).where(Collection.embedding_preset_id == preset_id)
            )
        ).all()
    for name in names:
        await invalidate(name)
