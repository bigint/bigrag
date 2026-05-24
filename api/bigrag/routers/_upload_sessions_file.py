from __future__ import annotations

from fastapi import Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.models.upload_session import UploadSessionFileResponse
from bigrag.routers import enforce_collection_pin, ensure_embedding_or_400, get_collection_or_404
from bigrag.routers.upload_sessions import router
from bigrag.services.upload_session_files import upload_session_file_response


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
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    ensure_embedding_or_400(collection)
    return await upload_session_file_response(
        collection_name=collection_name,
        collection=collection,
        session_id=session_id,
        request=request,
        file=file,
        client_item_id=client_item_id,
        user=user,
        db=db,
    )
