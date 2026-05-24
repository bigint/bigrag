from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.logging import get_logger
from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.services.document_progress import publish_queued_progress
from bigrag.services.documents import content_hash_match, persist_document
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.upload_session_files.types import (
    PersistedUpload,
    StagedUpload,
    UploadSessionFileContext,
)
from bigrag.services.upload_session_items import existing_item, fail_item, reserve_item
from bigrag.services.upload_sessions import item_response, upload_session_response

logger = get_logger("bigrag.services.upload_session_files")


async def persist_upload(
    db: AsyncSession,
    context: UploadSessionFileContext,
    collection_name: str,
    collection: dict,
    staged: StagedUpload,
) -> PersistedUpload | UploadSessionFileResponse:
    item = context.existing
    try:
        item = await reserve_item(
            db,
            context.upload_session,
            context.existing,
            context.item_key,
            context.filename,
            context.file_ext,
            staged.size,
            staged.content_hash,
        )
        existing_doc = await db.scalar(
            content_hash_match(collection, staged.content_hash, context.upload_session.meta or {})
        )
        if existing_doc is None:
            doc = await persist_document(
                session=db,
                collection_name=collection_name,
                collection=collection,
                filename=context.filename,
                source=staged.path,
                file_size=staged.size,
                metadata=context.upload_session.meta or {},
                content_hash=staged.content_hash,
                raise_on_enqueue_failure=False,
            )
            publish_queued_progress(doc, collection_name, "Queued from upload session")
        else:
            doc = existing_doc
    except IntegrityError:
        await db.rollback()
        duplicate = await existing_item(db, context.upload_session.id, context.item_key)
        if duplicate is None:
            raise
        response = await upload_session_response(db, context.upload_session, persist_counts=True)
        return UploadSessionFileResponse(
            item=item_response(duplicate, None, None),
            session=response,
        )
    except Exception as exc:
        logger.exception(
            "upload_session.persist_failed",
            collection=collection_name,
            session_id=str(context.upload_session.id),
            filename=context.filename,
        )
        safe_message = sanitize_message_text(str(exc)) or "upload failed"
        failure_message = f"upload failed: {safe_message}"
        if item is None:
            await db.rollback()
            failed = await fail_item(
                db,
                context.upload_session,
                context.item_key,
                context.filename,
                context.file_ext,
                failure_message,
                file_size=staged.size,
                content_hash=staged.content_hash,
            )
        else:
            item.status = "failed"
            item.error_message = failure_message
            await db.commit()
            await db.refresh(item)
            failed = item
        response = await upload_session_response(db, context.upload_session, persist_counts=True)
        return UploadSessionFileResponse(
            item=item_response(failed, None, failed.error_message),
            session=response,
        )

    return PersistedUpload(item=item, document=doc, deduped=existing_doc is not None)
