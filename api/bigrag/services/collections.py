from __future__ import annotations

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.logging import get_logger
from bigrag.services import collection_cache
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.staged_files import delete_staged_collection_prefix
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.services.collections")


async def delete_collection(session: AsyncSession, name: str) -> str:
    logger.info("delete collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    flushed = await ingestion_queue.cancel_collection(name)
    logger.info("delete collection jobs cancelled", collection=name, flushed=flushed)

    deleted_id = str(collection.id)
    deleted = await delete_staged_collection_prefix(name)
    logger.info("delete collection staging removed", collection=name, count=deleted)

    await vector_store.delete_collection(name)
    logger.info("delete collection vectors dropped", collection=name)

    await session.delete(collection)
    await session.commit()
    await collection_cache.invalidate(name)
    await invalidate_collection_query_cache(name)
    logger.info("delete collection database records removed", collection=name)

    return deleted_id


async def truncate_collection(session: AsyncSession, name: str) -> str:
    logger.info("truncate collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    flushed = await ingestion_queue.cancel_collection(name)
    logger.info("truncate collection jobs cancelled", collection=name, flushed=flushed)

    collection_id = str(collection.id)
    deleted = await delete_staged_collection_prefix(name)
    logger.info("truncate collection staging removed", collection=name, count=deleted)

    await vector_store.delete_collection(name)
    logger.info("truncate collection vectors cleared", collection=name)

    await session.execute(sa.delete(Document).where(Document.collection_id == collection.id))
    await session.execute(
        sa.update(Collection).where(Collection.id == collection.id).values(document_count=0)
    )
    await session.commit()
    await collection_cache.invalidate(name)
    await invalidate_collection_query_cache(name)
    logger.info("truncate collection documents removed", collection=name)

    return collection_id
