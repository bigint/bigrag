from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement
from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.multimodal import DocumentElementListResponse, DocumentElementResponse
from bigrag.routers import enforce_collection_pin, get_collection_or_404
from bigrag.routers.documents._router import router
from bigrag.routers.documents_uploads import uuid_or_404
from bigrag.services.documents import check_document_tenant
from bigrag.services.vector_store import vector_store


@router.get("/{document_id}/elements", response_model=DocumentElementListResponse)
async def get_document_elements(
    collection_name: str,
    document_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentElementListResponse:
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    doc_id = uuid_or_404(document_id, "Document")
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == doc_id)
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    check_document_tenant(user, doc, collection)

    total = await session.scalar(
        sa.select(sa.func.count())
        .select_from(DocumentElement)
        .where(DocumentElement.document_id == doc_id)
        .where(DocumentElement.collection_id == collection["id"])
    )
    rows = (
        await session.scalars(
            sa.select(DocumentElement)
            .where(DocumentElement.document_id == doc_id)
            .where(DocumentElement.collection_id == collection["id"])
            .order_by(DocumentElement.element_index.asc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return DocumentElementListResponse(
        elements=[_document_element_response(row) for row in rows],
        total=total or 0,
    )


@router.get("/{document_id}/chunks", response_model=dict[str, object])
async def get_document_chunks(
    collection_name: str,
    document_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid_or_404(document_id, "Document"))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    check_document_tenant(user, doc, collection)

    chunks = await vector_store.get_chunks(
        collection_name,
        document_id,
        limit=limit,
        offset=offset,
    )
    return {"chunks": chunks, "total": doc.chunk_count}


def _document_element_response(row: DocumentElement) -> DocumentElementResponse:
    return DocumentElementResponse(
        id=str(row.id),
        document_id=str(row.document_id),
        collection_id=str(row.collection_id),
        element_index=row.element_index,
        kind=row.kind,
        text=row.text,
        summary=row.summary,
        caption=row.caption,
        asset_path=row.asset_path,
        page_no=row.page_no,
        bbox=row.bbox,
        char_start=row.char_start,
        char_end=row.char_end,
        surrounding_context=row.surrounding_context,
        metadata=row.meta or {},
        enrichment_status=row.enrichment_status,
        enrichment_error=row.enrichment_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
