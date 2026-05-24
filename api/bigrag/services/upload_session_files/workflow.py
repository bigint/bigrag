from __future__ import annotations

from fastapi import Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.services.upload_session_files.context import load_context
from bigrag.services.upload_session_files.persistence import persist_upload
from bigrag.services.upload_session_files.responses import success_response, unlink_staged
from bigrag.services.upload_session_files.staging import stage_file


async def upload_session_file_response(
    *,
    collection_name: str,
    collection: dict,
    session_id: str,
    request: Request,
    file: UploadFile,
    client_item_id: str | None,
    user: dict,
    db: AsyncSession,
) -> UploadSessionFileResponse:
    context = await load_context(
        db=db,
        collection=collection,
        session_id=session_id,
        file=file,
        client_item_id=client_item_id,
        user=user,
    )
    if isinstance(context, UploadSessionFileResponse):
        return context

    staged = await stage_file(db, context, file)
    if isinstance(staged, UploadSessionFileResponse):
        return staged

    try:
        persisted = await persist_upload(db, context, collection_name, collection, staged)
        if isinstance(persisted, UploadSessionFileResponse):
            return persisted
        return await success_response(
            db=db,
            request=request,
            user=user,
            collection_name=collection_name,
            context=context,
            persisted=persisted,
            staged=staged,
        )
    finally:
        unlink_staged(staged.path)
