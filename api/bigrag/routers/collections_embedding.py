from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.routers.collections import router
from bigrag.services import audit
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.routers.collections_embedding")


@router.post("/{name}/reembed", response_model=StatusResponse)
async def reembed_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:

    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    docs = (
        await session.execute(
            sa.select(Document.id, Document.file_path)
            .where(Document.collection_id == collection.id)
            .where(Document.status.in_(("ready", "failed")))
        )
    ).all()

    collection_dict = {
        "embedding_provider": collection.embedding_provider,
        "embedding_model": collection.embedding_model,
        "embedding_api_key": collection.embedding_api_key,
        "embedding_base_url": collection.embedding_base_url,
        "dimension": collection.dimension,
        "chunk_size": collection.chunk_size,
        "chunk_overlap": collection.chunk_overlap,
        "chunk_strategy": collection.chunk_strategy or "paragraph",
        "tenant_field": collection.tenant_field,
    }
    jobs = [
        create_ingestion_job(
            document_id=str(doc_id),
            file_path=file_path,
            collection_name=name,
            collection=collection_dict,
        )
        for doc_id, file_path in docs
    ]

    doc_ids = [doc_id for doc_id, _ in docs]
    for doc_id in doc_ids:
        await vector_store.delete_by_document(name, str(doc_id))
    await session.execute(
        sa.update(Document)
        .where(Document.id.in_(doc_ids))
        .values(status="pending", error_message=None)
    )
    await session.commit()

    for job in jobs:
        await ingestion_queue.enqueue(job)
    await invalidate_collection_query_cache(name)

    logger.info("reembed: queued", collection=name, docs=len(docs))
    audit.record(
        request,
        user=user,
        action="collection.reembed",
        resource_type="collection",
        resource_id=str(collection.id),
        metadata={"name": name, "docs_queued": len(docs)},
    )
    await enqueue_webhook_event(
        "collection.reembed.queued",
        collection=name,
        data={
            "collection_id": str(collection.id),
            "name": name,
            "docs_queued": len(docs),
        },
    )
    return StatusResponse(
        status="ok",
        message=f"Queued {len(docs)} documents for re-embedding",
    )
