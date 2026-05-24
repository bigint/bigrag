from __future__ import annotations

from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.services import audit, collection_cache
from bigrag.services.document_progress import document_progress
from bigrag.services.documents import document_response
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.upload_session_files.types import (
    PersistedUpload,
    StagedUpload,
    UploadSessionFileContext,
)
from bigrag.services.upload_session_items import fail_item
from bigrag.services.upload_sessions import item_response, upload_session_response


async def success_response(
    *,
    db: AsyncSession,
    request: Request,
    user: dict,
    collection_name: str,
    context: UploadSessionFileContext,
    persisted: PersistedUpload,
    staged: StagedUpload,
) -> UploadSessionFileResponse:
    item = persisted.item
    doc = persisted.document
    item.document_id = doc.id
    item.filename = context.filename
    item.file_type = context.file_ext.lstrip(".")
    item.file_size = staged.size
    item.content_hash = staged.content_hash
    item.storage_key = None
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
        resource_id=str(context.upload_session.id),
        metadata={"collection": collection_name, "filename": context.filename, "size": staged.size},
    )
    response = await upload_session_response(db, context.upload_session, persist_counts=True)
    item_progress = await document_progress(doc, collection_name)
    doc_payload = document_response(doc, deduped=persisted.deduped, progress=item_progress)
    return UploadSessionFileResponse(
        item=item_response(item, doc_payload.status, doc_payload.error_message),
        session=response,
    )


async def failure_response(
    db: AsyncSession,
    context: UploadSessionFileContext,
    message: str,
    *,
    file_size: int = 0,
    content_hash: str | None = None,
) -> UploadSessionFileResponse:
    item = await fail_item(
        db,
        context.upload_session,
        context.item_key,
        context.filename,
        context.file_ext,
        message,
        file_size=file_size,
        content_hash=content_hash,
    )
    response = await upload_session_response(db, context.upload_session, persist_counts=True)
    return UploadSessionFileResponse(
        item=item_response(item, None, item.error_message),
        session=response,
    )


def unlink_staged(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
