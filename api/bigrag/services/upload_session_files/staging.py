from __future__ import annotations

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.services.documents import SUPPORTED_EXTENSIONS, stream_upload_to_temp
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.runtime_settings import get_values
from bigrag.services.upload_session_files.responses import failure_response, unlink_staged
from bigrag.services.upload_session_files.types import StagedUpload, UploadSessionFileContext


async def stage_file(
    db: AsyncSession,
    context: UploadSessionFileContext,
    file: UploadFile,
) -> StagedUpload | UploadSessionFileResponse:
    unsupported = unsupported_file_message(context.file_ext)
    if unsupported is not None:
        return await failure_response(db, context, unsupported)

    limits = await get_values(["max_upload_size_mb", "max_upload_session_size_mb"])
    try:
        tmp_path, content_hash, size = await stream_upload_to_temp(
            file,
            max_size=limits["max_upload_size_mb"] * 1024 * 1024,
        )
    except HTTPException as exc:
        return await failure_response(db, context, str(exc.detail))

    staged = StagedUpload(path=tmp_path, content_hash=content_hash, size=size)
    rejection = await staged_rejection(db, context, staged, limits)
    if rejection is not None:
        unlink_staged(tmp_path)
        return rejection
    return staged


def unsupported_file_message(file_ext: str) -> str | None:
    if not file_ext or file_ext in SUPPORTED_EXTENSIONS:
        return None
    supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
    return f"Unsupported file type '{file_ext}'. Supported: {supported}"


async def staged_rejection(
    db: AsyncSession,
    context: UploadSessionFileContext,
    staged: StagedUpload,
    limits: dict,
) -> UploadSessionFileResponse | None:
    if staged.size == 0:
        return await failure_response(
            db,
            context,
            "File is empty",
            file_size=staged.size,
            content_hash=staged.content_hash,
        )

    uploaded_bytes = sum(
        item.file_size for item, _status, _error in context.rows if item.status != "failed"
    )
    max_session_bytes = limits["max_upload_session_size_mb"] * 1024 * 1024
    existing_size = context.existing.file_size if context.existing is not None else 0
    if uploaded_bytes - existing_size + staged.size > max_session_bytes:
        return await failure_response(
            db,
            context,
            f"Upload session too large. Max size: {limits['max_upload_session_size_mb']}MB",
            file_size=staged.size,
            content_hash=staged.content_hash,
        )

    try:
        await validate_upload(staged.path, context.file_ext)
    except InvalidFileContentError as exc:
        safe_message = sanitize_message_text(str(exc)) or "Invalid file content"
        return await failure_response(
            db,
            context,
            safe_message,
            file_size=staged.size,
            content_hash=staged.content_hash,
        )
    return None
