from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.models.document import DocumentListResponse, DocumentResponse
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.document_progress import document_progress, document_progress_map
from bigrag.services.documents.serialize import document_response
from bigrag.services.documents.tenant import check_document_tenant, document_tenant_metadata_filter
from bigrag.services.pagination import paginate
from bigrag.services.tenant_enforcement import tenant_field

_DOCUMENT_SORT_COLUMNS = {
    "created_at": Document.created_at,
    "updated_at": Document.updated_at,
    "filename": Document.filename,
    "file_size": Document.file_size,
    "chunk_count": Document.chunk_count,
    "status": Document.status,
}


async def list_documents_payload(
    session: AsyncSession,
    *,
    collection_name: str,
    q: str | None,
    status: str | None,
    sort: str,
    order: str,
    limit: int,
    offset: int,
    cursor: str | None,
    include_total: bool,
    user: dict,
) -> DocumentListResponse:
    collection = await get_collection_or_404(collection_name)
    sort_column = _DOCUMENT_SORT_COLUMNS.get(sort)
    if sort_column is None:
        raise HTTPException(status_code=400, detail="Invalid document sort")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid document order")

    stmt = (
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .order_by(
            sort_column.asc() if order == "asc" else sort_column.desc(),
            Document.id.asc() if order == "asc" else Document.id.desc(),
        )
    )
    count_stmt = (
        sa.select(sa.func.count())
        .select_from(Document)
        .where(Document.collection_id == collection["id"])
    )
    search_term = q.strip() if q else ""
    if search_term:
        pattern = f"%{search_term}%"
        search_filter = sa.or_(
            Document.filename.ilike(pattern),
            Document.file_type.ilike(pattern),
            Document.error_message.ilike(pattern),
            sa.cast(Document.id, sa.Text).ilike(pattern),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)
    if status:
        stmt = stmt.where(Document.status == status)
        count_stmt = count_stmt.where(Document.status == status)
    tenant_filter = document_tenant_metadata_filter(user, collection)
    if tenant_filter is not None:
        stmt = stmt.where(Document.meta.contains(tenant_filter))
        count_stmt = count_stmt.where(Document.meta.contains(tenant_filter))

    if cursor and sort != "created_at":
        raise HTTPException(
            status_code=400,
            detail="cursor pagination requires sort=created_at",
        )

    result = await paginate(
        session,
        stmt,
        created_col=Document.created_at,
        id_col=Document.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=count_stmt if include_total else None,
        direction=order,
    )

    progresses = await document_progress_map(result.rows, collection_name)
    documents = [document_response(doc, progress=progresses[str(doc.id)]) for doc in result.rows]

    return DocumentListResponse(
        documents=documents, total=result.total, next_cursor=result.next_cursor
    )


async def get_document_payload(
    session: AsyncSession,
    *,
    user: dict,
    collection_name: str,
    document_id: str,
) -> DocumentResponse:
    collection = await get_collection_or_404(collection_name)
    try:
        target_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == target_id)
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    check_document_tenant(user, doc, collection)
    return document_response(doc, progress=await document_progress(doc, collection_name))


def content_hash_match(
    collection: dict,
    content_hash: str,
    metadata: dict,
) -> sa.Select:
    stmt = (
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .where(Document.content_hash == content_hash)
        .limit(1)
    )
    field = tenant_field(collection)
    if field:
        stmt = stmt.where(Document.meta.contains({field: metadata[field]}))
    return stmt


async def get_document_with_collection(
    session: AsyncSession,
    document_id: str,
    *,
    principal: dict,
) -> tuple[Document, str]:
    try:
        target_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    pinned_collection = principal.get("collection")
    stmt = (
        sa.select(Document, Collection.name)
        .join(Collection, Collection.id == Document.collection_id)
        .where(Document.id == target_id)
    )
    if pinned_collection:
        stmt = stmt.where(Collection.name == pinned_collection)
    row = (await session.execute(stmt)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, collection_name = row
    return doc, collection_name
