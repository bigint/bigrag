from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.models.collection import CollectionResponse, UpdateCollectionRequest
from bigrag.routers import enforce_collection_pin
from bigrag.routers.collections._router import router
from bigrag.routers.collections.serializers import collection_response
from bigrag.services import audit, collection_cache
from bigrag.services.collections import apply_collection_update
from bigrag.services.collections import delete_collection as service_delete_collection
from bigrag.services.collections import truncate_collection as service_truncate_collection
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.routers.collections")


@router.put("/{name}", response_model=CollectionResponse)
async def update_collection(
    name: str,
    body: UpdateCollectionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("update collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    fields = await apply_collection_update(collection, body)

    await session.commit()
    await session.refresh(collection)
    await collection_cache.invalidate(name)
    await invalidate_collection_query_cache(name)

    audit.record(
        request,
        user=user,
        action="collection.update",
        resource_type="collection",
        resource_id=str(collection.id),
        metadata={"name": name, "fields": fields},
    )
    await enqueue_webhook_event(
        "collection.updated",
        collection=collection.name,
        data={
            "collection_id": str(collection.id),
            "name": collection.name,
            "fields": fields,
        },
    )
    return collection_response(collection)


@router.delete("/{name}", response_model=StatusResponse)
async def delete_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    deleted_id = await service_delete_collection(session, name)
    audit.record(
        request,
        user=user,
        action="collection.delete",
        resource_type="collection",
        resource_id=deleted_id,
        metadata={"name": name},
    )
    await enqueue_webhook_event(
        "collection.deleted",
        collection=name,
        data={"collection_id": deleted_id, "name": name},
    )
    return StatusResponse(status="ok", message=f"Collection '{name}' deleted")


@router.post("/{name}/truncate", response_model=StatusResponse)
async def truncate_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    collection_id = await service_truncate_collection(session, name)
    audit.record(
        request,
        user=user,
        action="collection.truncate",
        resource_type="collection",
        resource_id=collection_id,
        metadata={"name": name},
    )
    await enqueue_webhook_event(
        "collection.truncated",
        collection=name,
        data={"collection_id": collection_id, "name": name},
    )
    return StatusResponse(status="ok", message=f"Collection '{name}' truncated")
