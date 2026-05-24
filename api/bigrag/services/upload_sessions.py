from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, UploadSession, UploadSessionItem
from bigrag.models.upload_session import UploadSessionItemResponse, UploadSessionResponse
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404

TERMINAL_SESSION_STATUSES = {"complete", "failed", "canceled"}


def deleted_document_item(item: UploadSessionItem, document_status: str | None) -> bool:
    return item.document_id is None and document_status is None


def effective_item_status(item: UploadSessionItem, document_status: str | None) -> str:
    if item.status in {"failed", "canceled"}:
        return item.status
    if deleted_document_item(item, document_status):
        return "canceled"
    if document_status == "ready":
        return "complete"
    if document_status == "failed":
        return "failed"
    if document_status == "processing":
        return "ingesting"
    return "queued"


def item_response(
    item: UploadSessionItem,
    document_status: str | None,
    document_error: str | None,
) -> UploadSessionItemResponse:
    status = effective_item_status(item, document_status)
    error_message = item.error_message or document_error
    if status == "canceled" and deleted_document_item(item, document_status):
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


async def session_rows(
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


def session_counts(
    rows: list[tuple[UploadSessionItem, str | None, str | None]],
) -> dict[str, int]:
    counts = {
        "uploaded_files": len(rows),
        "queued_files": 0,
        "processing_files": 0,
        "completed_files": 0,
        "failed_files": 0,
        "canceled_files": 0,
    }
    for item, status, _error in rows:
        effective = effective_item_status(item, status)
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


def session_status_value(upload_session: UploadSession, counts: dict[str, int]) -> str:
    if upload_session.status == "canceled":
        return "canceled"
    active = counts["queued_files"] + counts["processing_files"]
    if counts["uploaded_files"] < upload_session.total_files:
        return "uploading" if counts["uploaded_files"] else "preparing"
    if active:
        return "ingesting"
    if not counts["completed_files"] and (counts["failed_files"] or counts["canceled_files"]):
        return "failed"
    return "complete"


async def upload_session_response(
    db: AsyncSession,
    upload_session: UploadSession,
    *,
    persist_counts: bool = False,
) -> UploadSessionResponse:
    rows = await session_rows(db, upload_session.id)
    counts = session_counts(rows)
    status = session_status_value(upload_session, counts)
    active = counts["queued_files"] + counts["processing_files"]
    if persist_counts:
        for item, document_status, _error in rows:
            if deleted_document_item(item, document_status):
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
        rows = await session_rows(db, upload_session.id)
        counts = session_counts(rows)
        status = session_status_value(upload_session, counts)
        active = counts["queued_files"] + counts["processing_files"]
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
        recent_items=[item_response(item, status, error) for item, status, error in rows[:20]],
        metadata=upload_session.meta or {},
        created_at=upload_session.created_at,
        updated_at=upload_session.updated_at,
        closed_at=upload_session.closed_at,
    )


async def get_upload_session(
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


async def get_upload_session_for_update(
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


async def upload_session_payload(
    db: AsyncSession,
    *,
    user: dict,
    collection_name: str,
    session_id: str,
) -> UploadSessionResponse:
    collection = await get_collection_or_404(collection_name)
    upload_session = await get_upload_session(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    return await upload_session_response(db, upload_session, persist_counts=True)
