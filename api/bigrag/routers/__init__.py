from __future__ import annotations

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config

__all__ = [
    "get_collection_or_404",
    "get_embedding_model_for",
    "get_reranking_config",
    "validate_collection_name",
]


async def validate_collection_name(session: AsyncSession, collection: str | None) -> str | None:
    if collection is None:
        return None
    name = collection.strip()
    if not name:
        return None
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=400, detail=f"Collection {name!r} does not exist")
    return name
