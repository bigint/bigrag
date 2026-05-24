from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, UploadSession
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.models.upload_session import (
    UploadSessionCreateRequest,
    UploadSessionResponse,
)
from bigrag.routers import enforce_collection_pin, ensure_embedding_or_400, get_collection_or_404
from bigrag.routers._upload_sessions import (
    effective_item_status as _effective_item_status,
)
from bigrag.routers._upload_sessions import (
    get_upload_session as _get_upload_session,
)
from bigrag.routers._upload_sessions import (
    get_upload_session_for_update as _get_upload_session_for_update,
)
from bigrag.routers._upload_sessions import (
    session_rows as _session_rows,
)
from bigrag.routers._upload_sessions import (
    upload_session_response,
)
from bigrag.services import audit
from bigrag.services.documents import prepare_document_metadata
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import get_values
from bigrag.services.staged_files import delete_staged_file_path
from bigrag.services.tenant_enforcement import enforce_tenant_metadata

logger = get_logger("bigrag.routers.upload_sessions")

router = APIRouter(
    prefix="/v1/collections/{collection_name}/upload-sessions",
    tags=["upload-sessions"],
)


@router.post("", response_model=UploadSessionResponse, status_code=201)
async def create_upload_session(
    collection_name: str,
    body: UploadSessionCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    ensure_embedding_or_400(collection)
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
    meta = enforce_tenant_metadata(collection, meta, user, label="metadata")
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
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    upload_session = await _get_upload_session(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    return await upload_session_response(db, upload_session, persist_counts=True)


@router.post("/{session_id}/complete", response_model=UploadSessionResponse)
async def complete_upload_session(
    collection_name: str,
    session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
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
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    upload_session = await _get_upload_session_for_update(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    rows = await _session_rows(db, upload_session.id)
    document_ids = [str(item.document_id) for item, _status, _error in rows if item.document_id]
    if document_ids:
        await ingestion_queue.cancel_documents(document_ids)
    pending_document_ids = {
        item.document_id
        for item, status, _error in rows
        if item.document_id and _effective_item_status(item, status) == "queued"
    }
    for document_id in pending_document_ids:
        doc = await db.get(Document, document_id)
        if doc is not None and doc.status == "pending":
            if await delete_staged_file_path(doc.file_path):
                doc.file_path = ""
            doc.status = "failed"
            doc.error_message = "Upload session canceled"
    for item, status, _error in rows:
        if _effective_item_status(item, status) in {"queued", "ingesting"}:
            item.status = "canceled"
            item.error_message = "Upload session canceled"
            item.storage_key = None
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
