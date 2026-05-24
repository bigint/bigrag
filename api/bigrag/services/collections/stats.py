from __future__ import annotations

import random

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.models.collection import CollectionStatsResponse
from bigrag.services import collection_cache, redis_cache
from bigrag.services.runtime_settings import get_value


async def collection_stats_payload(
    session: AsyncSession,
    *,
    name: str,
) -> CollectionStatsResponse:
    collection = await collection_cache.get_or_404(name)
    cache_key = f"collection_stats:{collection['id']}"
    cached = await redis_cache.get(cache_key)
    if isinstance(cached, dict):
        return CollectionStatsResponse(**cached)

    stats = (
        await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("total_chunks"),
                sa.func.coalesce(sa.func.sum(Document.token_count), 0).label("total_tokens"),
                sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("total_size"),
                sa.func.count().label("document_count"),
                sa.func.count().filter(Document.status == "ready").label("ready"),
                sa.func.count().filter(Document.status == "pending").label("pending"),
                sa.func.count().filter(Document.status == "processing").label("processing"),
                sa.func.count().filter(Document.status == "failed").label("failed"),
            ).where(Document.collection_id == collection["id"])
        )
    ).one()

    response = CollectionStatsResponse(
        collection=name,
        document_count=stats.document_count,
        total_chunks=int(stats.total_chunks),
        total_tokens=int(stats.total_tokens),
        total_size_bytes=int(stats.total_size),
        status_counts={
            "ready": stats.ready,
            "pending": stats.pending,
            "processing": stats.processing,
            "failed": stats.failed,
        },
    )
    ttl = await get_value("collection_cache_ttl")
    if ttl > 0:
        await redis_cache.set(
            cache_key, response.model_dump(), ttl=ttl + random.randint(0, max(1, ttl // 10))
        )
    return response
