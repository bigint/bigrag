from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.models.document import BatchStatusResponse, DocumentStatusResponse
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.document_progress import document_progress_map
from bigrag.services.tenant_enforcement import document_tenant_allowed


async def batch_status_payload(
    session: AsyncSession,
    *,
    user: dict,
    collection_name: str,
    document_ids: list[str],
) -> BatchStatusResponse:
    collection = await get_collection_or_404(collection_name)

    if len(document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch status")

    uuids = [_document_uuid(d) for d in document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()
    docs = [d for d in docs if document_tenant_allowed(user, collection, d.meta)]

    progresses = await document_progress_map(list(docs), collection_name)
    documents = [
        DocumentStatusResponse(
            id=str(doc.id),
            status=doc.status,
            error_message=doc.error_message,
            chunk_count=doc.chunk_count,
            multimodal_element_count=doc.multimodal_element_count,
            progress=progresses[str(doc.id)],
        )
        for doc in docs
    ]

    return BatchStatusResponse(documents=documents, total=len(documents))


def _document_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
