from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.ids import uuid7
from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.services.upload_session_files.types import UploadSessionFileContext
from bigrag.services.upload_session_items import existing_item
from bigrag.services.upload_sessions import (
    TERMINAL_SESSION_STATUSES,
    get_upload_session_for_update,
    item_response,
    session_rows,
    upload_session_response,
)


async def load_context(
    *,
    db: AsyncSession,
    collection: dict,
    session_id: str,
    file: UploadFile,
    client_item_id: str | None,
    user: dict,
) -> UploadSessionFileContext | UploadSessionFileResponse:
    upload_session = await get_upload_session_for_update(
        db,
        collection["id"],
        session_id,
        user_id=uuid.UUID(user["id"]),
    )
    if upload_session.status in TERMINAL_SESSION_STATUSES:
        raise HTTPException(status_code=409, detail="Upload session is closed")

    item_key = client_item_id or str(uuid7())
    existing = await existing_item(db, upload_session.id, item_key)
    if existing is not None and existing.status != "failed":
        response = await upload_session_response(db, upload_session, persist_counts=True)
        return UploadSessionFileResponse(item=item_response(existing, None, None), session=response)

    rows = await session_rows(db, upload_session.id)
    if existing is None and len(rows) >= upload_session.total_files:
        raise HTTPException(status_code=400, detail="Upload session file count is already complete")

    await db.commit()
    filename = file.filename or "document"
    return UploadSessionFileContext(
        upload_session=upload_session,
        existing=existing,
        rows=rows,
        item_key=item_key,
        filename=filename,
        file_ext=Path(filename).suffix.lower(),
    )
