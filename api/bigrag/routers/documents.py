from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.models.document import (
    DocumentListResponse,
    DocumentResponse,
)
from bigrag.models.multimodal import DocumentElementListResponse, DocumentElementResponse
from bigrag.routers import enforce_collection_pin, ensure_embedding_or_400, get_collection_or_404
from bigrag.routers._documents import (
    check_document_tenant,
    document_response,
    parse_form_metadata,
)
from bigrag.routers.documents_progress import (
    document_progress,
    document_progress_map,
    publish_queued_progress,
)
from bigrag.routers.documents_uploads import (
    metadata_or_400,
    upload_extension_or_400,
    uuid_or_404,
    validated_upload_to_temp,
)
from bigrag.services import audit, collection_cache
from bigrag.services.documents import (
    content_hash_match,
    persist_document,
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.staged_files import StagedFileCleanupError, delete_staged_file_path
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.routers.documents")

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    collection_name: str,
    request: Request,
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    ensure_embedding_or_400(collection)
    logger.info("document upload", collection=collection_name, filename=file.filename)

    file_ext = upload_extension_or_400(file.filename)

    upload_limits = await get_values(["max_upload_size_mb"])
    max_upload_size_mb = upload_limits["max_upload_size_mb"]
    max_size = max_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {max_upload_size_mb}MB",
        )

    tmp_path, content_hash, file_size = await validated_upload_to_temp(
        file, file_ext, max_size=max_size
    )
    try:
        meta = metadata_or_400(collection, metadata, prepare_document_metadata, parse_form_metadata)

        existing = await session.scalar(content_hash_match(collection, content_hash, meta))
        if existing is not None:
            logger.info(
                "upload: dedup hit — returning existing doc",
                content_hash=content_hash[:12],
                doc_id=str(existing.id),
            )
            return document_response(
                existing,
                deduped=True,
                progress=await document_progress(existing, collection_name),
            )

        try:
            doc = await persist_document(
                session=session,
                collection_name=collection_name,
                collection=collection,
                filename=file.filename or "document",
                source=tmp_path,
                file_size=file_size,
                metadata=meta,
                content_hash=content_hash,
                raise_on_enqueue_failure=True,
            )
        except IntegrityError:
            existing = await session.scalar(content_hash_match(collection, content_hash, meta))
            if existing is not None:
                logger.info(
                    "upload: integrity dedup hit — returning existing doc",
                    content_hash=content_hash[:12],
                    doc_id=str(existing.id),
                )
                return document_response(
                    existing,
                    deduped=True,
                    progress=await document_progress(existing, collection_name),
                )
            raise
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    publish_queued_progress(doc, collection_name, "Queued for ingestion")

    audit.record(
        request,
        user=user,
        action="document.upload",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={
            "collection": collection_name,
            "filename": doc.filename,
            "size": doc.file_size,
        },
    )
    return document_response(doc, progress=await document_progress(doc, collection_name))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_name: str,
    q: str | None = Query(default=None, max_length=200),
    status: str | None = None,
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=10000),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    sort_columns = {
        "created_at": Document.created_at,
        "updated_at": Document.updated_at,
        "filename": Document.filename,
        "file_size": Document.file_size,
        "chunk_count": Document.chunk_count,
        "status": Document.status,
    }
    sort_column = sort_columns.get(sort)
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

    if cursor and sort != "created_at":
        raise HTTPException(
            status_code=400,
            detail="cursor pagination requires sort=created_at",
        )
    cursor_tuple = decode_cursor_or_400(cursor)

    if cursor_tuple is not None:
        stmt = apply_cursor(
            stmt,
            Document.created_at,
            Document.id,
            cursor_tuple,
            direction=order,
        ).limit(limit + 1)
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (await session.scalar(count_stmt)) or 0
    progresses = await document_progress_map(page, collection_name)

    documents = [document_response(doc, progress=progresses[str(doc.id)]) for doc in page]

    return DocumentListResponse(documents=documents, total=total, next_cursor=next_cursor)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    collection_name: str,
    document_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
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
    return document_response(doc, progress=await document_progress(doc, collection_name))


@router.delete("/{document_id}", response_model=StatusResponse)
async def delete_document(
    collection_name: str,
    document_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid_or_404(document_id, "Document"))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await ingestion_queue.cancel_documents([document_id])

    file_path = doc.file_path
    deleted_filename = doc.filename
    try:
        await delete_staged_file_path(file_path, raise_on_failure=True)
    except StagedFileCleanupError as exc:
        raise HTTPException(
            status_code=503,
            detail="Staged file cleanup failed. Try deleting the document again.",
        ) from exc
    await vector_store.delete_by_document(
        collection_name,
        document_id,
    )
    await session.delete(doc)
    await recount_collection_documents(session, collection["id"])
    await session.commit()
    await collection_cache.invalidate(collection_name)
    await invalidate_collection_query_cache(collection_name)

    await enqueue_webhook_event(
        "document.deleted",
        collection=collection_name,
        data={
            "document_id": document_id,
            "collection": collection_name,
            "filename": deleted_filename,
        },
    )
    audit.record(
        request,
        user=user,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        metadata={"collection": collection_name, "filename": deleted_filename},
    )
    return StatusResponse(status="ok", message="Document deleted")


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
    exists = await session.scalar(
        sa.select(Document.id)
        .where(Document.id == doc_id)
        .where(Document.collection_id == collection["id"])
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Document not found")

    total = await session.scalar(
        sa.select(sa.func.count())
        .select_from(DocumentElement)
        .where(DocumentElement.document_id == doc_id)
    )
    rows = (
        await session.scalars(
            sa.select(DocumentElement)
            .where(DocumentElement.document_id == doc_id)
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
