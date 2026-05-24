from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.collection import CollectionResponse, CollectionStatsResponse
from bigrag.routers import enforce_collection_pin
from bigrag.routers.collections._router import router
from bigrag.routers.collections.serializers import collection_response
from bigrag.services.collections import collection_stats_payload

logger = get_logger("bigrag.routers.collections")


@router.get("/{name}", response_model=CollectionResponse)
async def get_collection(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("get collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection_response(collection)


@router.get("/{name}/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("collection stats", collection=name)
    return await collection_stats_payload(session, name=name)
