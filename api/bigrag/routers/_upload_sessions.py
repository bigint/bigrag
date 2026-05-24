from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import UploadSession, UploadSessionItem
from bigrag.services.upload_sessions import (
    TERMINAL_SESSION_STATUSES,
    effective_item_status,
    get_upload_session_for_update,
    item_response,
    session_rows,
    upload_session_response,
)

__all__ = [
    "TERMINAL_SESSION_STATUSES",
    "effective_item_status",
    "existing_item",
    "fail_item",
    "get_upload_session_for_update",
    "item_response",
    "reserve_item",
    "session_rows",
    "upload_session_response",
]


async def existing_item(
    db: AsyncSession,
    upload_session_id: uuid.UUID,
    client_item_id: str,
) -> UploadSessionItem | None:
    return await db.scalar(
        sa.select(UploadSessionItem)
        .where(UploadSessionItem.session_id == upload_session_id)
        .where(UploadSessionItem.client_item_id == client_item_id)
    )


async def fail_item(
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
    item = await existing_item(db, upload_session.id, client_item_id)
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


async def reserve_item(
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
