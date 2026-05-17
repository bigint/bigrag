from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, UploadSession, UploadSessionItem
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.common import StatusResponse
from bigrag.models.upload_session import (
    UploadSessionCreateRequest,
    UploadSessionFileResponse,
    UploadSessionItemResponse,
    UploadSessionResponse,
)
from bigrag.routers import get_collection_or_404, get_embedding_model_for
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    content_hash_match,
    document_response,
    persist_document,
    prepare_document_metadata,
    stream_upload_to_temp,
)
from bigrag.routers.documents_progress import document_progress, publish_queued_progress
from bigrag.services import audit, collection_cache
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.routers.upload_sessions")

router = APIRouter(
    prefix="/v1/collections/{collection_name}/upload-sessions",
    tags=["upload-sessions"],
)

TERMINAL_SESSION_STATUSES = {"complete", "failed", "canceled"}


def _deleted_document_item(item: UploadSessionItem, document_status: str | None) -> bool:
    return item.document_id is None and item.storage_key is not None and document_status is None


def _effective_item_status(item: UploadSessionItem, document_status: str | None) -> str:
    if _deleted_document_item(item, document_status):
        return "canceled"
    if item.status in {"failed", "canceled"}:
        return item.status
    if document_status == "ready":
        return "complete"
    if document_status == "failed":
        return "failed"
    if document_status == "processing":
        return "ingesting"
    return "queued"


def _item_response(
    item: UploadSessionItem,
    document_status: str | None,
    document_error: str | None,
) -> UploadSessionItemResponse:
    status = _effective_item_status(item, document_status)
    error_message = item.error_message or document_error
    if status == "canceled" and _deleted_document_item(item, document_status):
        error_message = error_message or "Document deleted"
    return UploadSessionItemResponse(
        id=str(item.id),
        client_item_id=item.client_item_id,
        document_id=str(item.document_id) if item.document_id else None,
        filename=item.filename,
        file_type=item.file_type,
        file_size=item.file_size,
        content_hash=item.content_hash,
        status=status,
        document_status=document_status,
        error_message=error_message,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _session_rows(
    db: AsyncSession,
    upload_session_id: uuid.UUID,
) -> list[tuple[UploadSessionItem, str | None, str | None]]:
    item_rank = sa.case(
        (Document.status.in_(("pending", "processing")), 0),
        (Document.status == "failed", 1),
        (UploadSessionItem.status.in_(("failed", "canceled")), 1),
        else_=2,
    )
    rows = (
        await db.execute(
            sa.select(UploadSessionItem, Document.status, Document.error_message)
            .outerjoin(Document, Document.id == UploadSessionItem.document_id)
            .where(UploadSessionItem.session_id == upload_session_id)
            .order_by(item_rank, UploadSessionItem.updated_at.desc())
        )
    ).all()
    return [(item, status, error) for item, status, error in rows]


def _counts(rows: list[tuple[UploadSessionItem, str | None, str | None]]) -> dict[str, int]:
    counts = {
        "uploaded_files": len(rows),
        "queued_files": 0,
        "processing_files": 0,
        "completed_files": 0,
        "failed_files": 0,
        "canceled_files": 0,
    }
    for item, status, _error in rows:
        effective = _effective_item_status(item, status)
        if effective == "queued":
            counts["queued_files"] += 1
        elif effective == "ingesting":
            counts["processing_files"] += 1
        elif effective == "complete":
            counts["completed_files"] += 1
        elif effective == "failed":
            counts["failed_files"] += 1
        elif effective == "canceled":
            counts["canceled_files"] += 1
    return counts


def _session_status(upload_session: UploadSession, counts: dict[str, int]) -> str:
    if upload_session.status == "canceled":
        return "canceled"
    active = counts["queued_files"] + counts["processing_files"]
    if counts["uploaded_files"] < upload_session.total_files:
        return "uploading" if counts["uploaded_files"] else "preparing"
    if active:
        return "ingesting"
    if counts["failed_files"] and not counts["completed_files"] and not counts["canceled_files"]:
        return "failed"
    return "complete"


async def upload_session_response(
    db: AsyncSession,
    upload_session: UploadSession,
    *,
    persist_counts: bool = False,
) -> UploadSessionResponse:
    rows = await _session_rows(db, upload_session.id)
    counts = _counts(rows)
    status = _session_status(upload_session, counts)
    active = counts["queued_files"] + counts["processing_files"]
    if persist_counts:
        for item, document_status, _error in rows:
            if _deleted_document_item(item, document_status):
                item.status = "canceled"
                item.error_message = item.error_message or "Document deleted"
        upload_session.status = status
        upload_session.uploaded_files = counts["uploaded_files"]
        upload_session.queued_files = counts["queued_files"]
        upload_session.completed_files = counts["completed_files"]
        upload_session.failed_files = counts["failed_files"]
        upload_session.canceled_files = counts["canceled_files"]
        if status in TERMINAL_SESSION_STATUSES and upload_session.closed_at is None:
            upload_session.closed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(upload_session)
    return UploadSessionResponse(
        id=str(upload_session.id),
        collection_id=str(upload_session.collection_id),
        collection_name=upload_session.collection_name,
        status=status,
        total_files=upload_session.total_files,
        total_bytes=upload_session.total_bytes,
        uploaded_files=counts["uploaded_files"],
        queued_files=counts["queued_files"],
        processing_files=counts["processing_files"],
        completed_files=counts["completed_files"],
        failed_files=counts["failed_files"],
        canceled_files=counts["canceled_files"],
        active_files=active,
        recent_items=[_item_response(item, status, error) for item, status, error in rows[:20]],
        metadata=upload_session.meta or {},
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
        closed_at=upload_session.closed_at,
    )


async def _get_upload_session(
    db: AsyncSession,
    collection_id: uuid.UUID,
    session_id: str,
    user_id: uuid.UUID | None = None,
) -> UploadSession:
    try:
        target = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Upload session not found") from exc
    stmt = (
        sa.select(UploadSession)
        .where(UploadSession.id == target)
        .where(UploadSession.collection_id == collection_id)
    )
    if user_id is not None:
        stmt = stmt.where(UploadSession.created_by == user_id)
    row = await db.scalar(stmt)
    if row is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return row


async def _get_upload_session_for_update(
    db: AsyncSession,
    collection_id: uuid.UUID,
    session_id: str,
    user_id: uuid.UUID | None = None,
) -> UploadSession:
    try:
        target = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Upload session not found") from exc
    stmt = (
        sa.select(UploadSession)
        .where(UploadSession.id == target)
        .where(UploadSession.collection_id == collection_id)
        .with_for_update()
    )
    if user_id is not None:
        stmt = stmt.where(UploadSession.created_by == user_id)
    row = await db.scalar(stmt)
    if row is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return row


async def _existing_item(
    db: AsyncSession,
    upload_session_id: uuid.UUID,
    client_item_id: str,
) -> UploadSessionItem | None:
    return await db.scalar(
        sa.select(UploadSessionItem)
        .where(UploadSessionItem.session_id == upload_session_id)
        .where(UploadSessionItem.client_item_id == client_item_id)
    )


async def _fail_item(
    db: AsyncSession,
    upload_session: UploadSession,
    client_item_id: str,
    filename: str,
    file_ext: str,
    message: str,
    *,
    file_size: int = 0,
    content_hash: str | None = None,
) -> UploadSessionItem:
    item = await _existing_item(db, upload_session.id, client_item_id)
    if item is None:
        item = UploadSessionItem(
            session_id=upload_session.id,
            client_item_id=client_item_id,
            filename=filename,
            file_type=file_ext.lstrip("."),
        )
        db.add(item)
    item.filename = filename
    item.file_type = file_ext.lstrip(".")
    item.file_size = file_size
    item.content_hash = content_hash
    item.status = "failed"
    item.error_message = message
    await db.commit()
    await db.refresh(item)
    return item


async def _reserve_item(
    db: AsyncSession,
    upload_session: UploadSession,
    existing: UploadSessionItem | None,
    client_item_id: str,
    filename: str,
    file_ext: str,
    file_size: int,
    content_hash: str,
) -> UploadSessionItem:
    item = existing or UploadSessionItem(
        session_id=upload_session.id, client_item_id=client_item_id
    )
    item.filename = filename
    item.file_type = file_ext.lstrip(".")
    item.file_size = file_size
    item.content_hash = content_hash
    item.status = "queued"
    item.error_message = None
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.post("", response_model=UploadSessionResponse, status_code=201)
async def create_upload_session(
    collection_name: str,
    body: UploadSessionCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    limits = await get_values(["max_upload_session_files", "max_upload_session_size_mb"])
    if body.total_files > limits["max_upload_session_files"]:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {limits['max_upload_session_files']} files per upload session",
        )
    max_session_bytes = limits["max_upload_session_size_mb"] * 1024 * 1024
    if body.total_bytes > max_session_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload session too large. Max size: {limits['max_upload_session_size_mb']}MB",
        )
    try:
        meta = prepare_document_metadata(collection, body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc
    upload_session = UploadSession(
        collection_id=collection["id"],
        collection_name=collection_name,
        total_files=body.total_files,
        total_bytes=body.total_bytes,
        created_by=uuid.UUID(user["id"]) if user.get("id") else None,
        meta=meta,
    )
    db.add(upload_session)
    await db.commit()
    await db.refresh(upload_session)
    audit.record(
        request,
        user=user,
        action="upload_session.create",
        resource_type="collection",
        resource_id=str(collection["id"]),
        metadata={
            "collection": collection_name,
            "total_files": body.total_files,
            "total_bytes": body.total_bytes,
        },
    )
    logger.info(
        "upload_session.create",
        collection=collection_name,
        session_id=str(upload_session.id),
        total_files=body.total_files,
    )
    return await upload_session_response(db, upload_session)


@router.get("/{session_id}", response_model=UploadSessionResponse)
async def get_upload_session(
    collection_name: str,
    session_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    upload_session = await _get_upload_session(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    return await upload_session_response(db, upload_session, persist_counts=True)


@router.post("/{session_id}/files", response_model=UploadSessionFileResponse, status_code=201)
async def upload_session_file(
    collection_name: str,
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
    client_item_id: str | None = Form(default=None),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    upload_session = await _get_upload_session_for_update(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    if upload_session.status in TERMINAL_SESSION_STATUSES:
        raise HTTPException(status_code=409, detail="Upload session is closed")
    item_key = client_item_id or str(uuid.uuid4())
    existing = await _existing_item(db, upload_session.id, item_key)
    if existing is not None and existing.status != "failed":
        response = await upload_session_response(db, upload_session, persist_counts=True)
        return UploadSessionFileResponse(
            item=_item_response(existing, None, None),
            session=response,
        )
    rows = await _session_rows(db, upload_session.id)
    if existing is None and len(rows) >= upload_session.total_files:
        raise HTTPException(status_code=400, detail="Upload session file count is already complete")
    filename = file.filename or "document"
    file_ext = Path(filename).suffix.lower()
    if file_ext and file_ext not in SUPPORTED_EXTENSIONS:
        item = await _fail_item(
            db,
            upload_session,
            item_key,
            filename,
            file_ext,
            (
                f"Unsupported file type '{file_ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )
        response = await upload_session_response(db, upload_session, persist_counts=True)
        return UploadSessionFileResponse(
            item=_item_response(item, None, item.error_message),
            session=response,
        )
    limits = await get_values(["max_upload_size_mb", "max_upload_session_size_mb"])
    try:
        tmp_path, content_hash, size = await stream_upload_to_temp(
            file,
            max_size=limits["max_upload_size_mb"] * 1024 * 1024,
        )
    except HTTPException as exc:
        item = await _fail_item(
            db,
            upload_session,
            item_key,
            filename,
            file_ext,
            str(exc.detail),
        )
        response = await upload_session_response(db, upload_session, persist_counts=True)
        return UploadSessionFileResponse(
            item=_item_response(item, None, item.error_message),
            session=response,
        )
    try:
        if size == 0:
            item = await _fail_item(
                db,
                upload_session,
                item_key,
                filename,
                file_ext,
                "File is empty",
                content_hash=content_hash,
            )
            response = await upload_session_response(db, upload_session, persist_counts=True)
            return UploadSessionFileResponse(
                item=_item_response(item, None, item.error_message),
                session=response,
            )
        uploaded_bytes = sum(
            item.file_size for item, _status, _error in rows if item.status != "failed"
        )
        max_session_bytes = limits["max_upload_session_size_mb"] * 1024 * 1024
        existing_size = existing.file_size if existing is not None else 0
        if uploaded_bytes - existing_size + size > max_session_bytes:
            item = await _fail_item(
                db,
                upload_session,
                item_key,
                filename,
                file_ext,
                f"Upload session too large. Max size: {limits['max_upload_session_size_mb']}MB",
                file_size=size,
                content_hash=content_hash,
            )
            response = await upload_session_response(db, upload_session, persist_counts=True)
            return UploadSessionFileResponse(
                item=_item_response(item, None, item.error_message),
                session=response,
            )
        try:
            await validate_upload(tmp_path, file_ext)
        except InvalidFileContentError as exc:
            item = await _fail_item(
                db,
                upload_session,
                item_key,
                filename,
                file_ext,
                str(exc),
                file_size=size,
                content_hash=content_hash,
            )
            response = await upload_session_response(db, upload_session, persist_counts=True)
            return UploadSessionFileResponse(
                item=_item_response(item, None, item.error_message),
                session=response,
            )
        item = await _reserve_item(
            db,
            upload_session,
            existing,
            item_key,
            filename,
            file_ext,
            size,
            content_hash,
        )
        try:
            existing_doc = await db.scalar(
                content_hash_match(collection, content_hash, upload_session.meta or {})
            )
            if existing_doc is None:
                doc = await persist_document(
                    session=db,
                    collection_name=collection_name,
                    collection=collection,
                    filename=filename,
                    source=tmp_path,
                    file_size=size,
                    metadata=upload_session.meta or {},
                    content_hash=content_hash,
                    raise_on_enqueue_failure=False,
                )
                publish_queued_progress(doc, collection_name, "Queued from upload session")
            else:
                doc = existing_doc
        except Exception as exc:
            logger.exception(
                "upload_session.persist_failed",
                collection=collection_name,
                session_id=str(upload_session.id),
                filename=filename,
            )
            item.status = "failed"
            item.error_message = f"upload failed: {exc}"
            await db.commit()
            await db.refresh(item)
            response = await upload_session_response(db, upload_session, persist_counts=True)
            return UploadSessionFileResponse(
                item=_item_response(item, None, item.error_message),
                session=response,
            )
        item.document_id = doc.id
        item.filename = filename
        item.file_type = file_ext.lstrip(".")
        item.file_size = size
        item.content_hash = content_hash
        item.storage_key = doc.file_path
        item.status = "failed" if doc.status == "failed" else "queued"
        item.error_message = doc.error_message if doc.status == "failed" else None
        db.add(item)
        await db.commit()
        await db.refresh(item)
        await collection_cache.invalidate(collection_name)
        await invalidate_collection_query_cache(collection_name)
        audit.record(
            request,
            user=user,
            action="upload_session.file",
            resource_type="upload_session",
            resource_id=str(upload_session.id),
            metadata={"collection": collection_name, "filename": filename, "size": size},
        )
        response = await upload_session_response(db, upload_session, persist_counts=True)
        item_progress = await document_progress(doc, collection_name)
        doc_payload = document_response(
            doc, deduped=existing_doc is not None, progress=item_progress
        )
        return UploadSessionFileResponse(
            item=_item_response(item, doc_payload.status, doc_payload.error_message),
            session=response,
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@router.post("/{session_id}/complete", response_model=UploadSessionResponse)
async def complete_upload_session(
    collection_name: str,
    session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    upload_session = await _get_upload_session_for_update(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    if upload_session.status == "canceled":
        raise HTTPException(status_code=409, detail="Upload session is canceled")
    upload_session.closed_at = upload_session.closed_at or datetime.now(UTC)
    await db.commit()
    await db.refresh(upload_session)
    audit.record(
        request,
        user=user,
        action="upload_session.complete",
        resource_type="upload_session",
        resource_id=str(upload_session.id),
        metadata={"collection": collection_name},
    )
    return await upload_session_response(db, upload_session, persist_counts=True)


@router.post("/{session_id}/cancel", response_model=StatusResponse)
async def cancel_upload_session(
    collection_name: str,
    session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    upload_session = await _get_upload_session(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    rows = await _session_rows(db, upload_session.id)
    document_ids = [str(item.document_id) for item, _status, _error in rows if item.document_id]
    if document_ids:
        await ingestion_queue.cancel_documents(document_ids)
    for item, status, _error in rows:
        if _effective_item_status(item, status) in {"queued", "ingesting"}:
            item.status = "canceled"
            item.error_message = "Upload session canceled"
    upload_session.status = "canceled"
    upload_session.closed_at = upload_session.closed_at or datetime.now(UTC)
    await db.commit()
    audit.record(
        request,
        user=user,
        action="upload_session.cancel",
        resource_type="upload_session",
        resource_id=str(upload_session.id),
        metadata={"collection": collection_name, "documents": len(document_ids)},
    )
    return StatusResponse(status="ok", message="Upload session canceled")
