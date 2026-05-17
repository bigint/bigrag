from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import UploadSession
from bigrag.db.session import get_session
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.common import StatusResponse
from bigrag.models.upload_session import (
    UploadSessionCreateRequest,
    UploadSessionFileResponse,
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
from bigrag.routers._upload_sessions import (
    TERMINAL_SESSION_STATUSES,
    upload_session_response,
)
from bigrag.routers._upload_sessions import (
    effective_item_status as _effective_item_status,
)
from bigrag.routers._upload_sessions import (
    existing_item as _existing_item,
)
from bigrag.routers._upload_sessions import (
    fail_item as _fail_item,
)
from bigrag.routers._upload_sessions import (
    get_upload_session as _get_upload_session,
)
from bigrag.routers._upload_sessions import (
    get_upload_session_for_update as _get_upload_session_for_update,
)
from bigrag.routers._upload_sessions import (
    item_response as _item_response,
)
from bigrag.routers._upload_sessions import (
    reserve_item as _reserve_item,
)
from bigrag.routers._upload_sessions import (
    session_rows as _session_rows,
)
from bigrag.routers.documents_progress import document_progress, publish_queued_progress
from bigrag.services import audit, collection_cache
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values

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
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        logger.warning("embedding model unavailable", collection=collection_name, error=repr(e))
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(e, "Embedding provider is not available for this collection."),
        ) from e
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
        logger.warning("embedding model unavailable", collection=collection_name, error=repr(e))
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(e, "Embedding provider is not available for this collection."),
        ) from e
    upload_session = await _get_upload_session_for_update(
        db, collection["id"], session_id, user_id=uuid.UUID(user["id"])
    )
    if upload_session.status in TERMINAL_SESSION_STATUSES:
        raise HTTPException(status_code=409, detail="Upload session is closed")
    item_key = client_item_id or str(uuid7())
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
    await db.commit()
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
        item = existing
        try:
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
        except IntegrityError:
            await db.rollback()
            duplicate = await _existing_item(db, upload_session.id, item_key)
            if duplicate is None:
                raise
            response = await upload_session_response(db, upload_session, persist_counts=True)
            return UploadSessionFileResponse(
                item=_item_response(duplicate, None, None),
                session=response,
            )
        except Exception as exc:
            logger.exception(
                "upload_session.persist_failed",
                collection=collection_name,
                session_id=str(upload_session.id),
                filename=filename,
            )
            if item is None:
                await db.rollback()
                item = await _fail_item(
                    db,
                    upload_session,
                    item_key,
                    filename,
                    file_ext,
                    f"upload failed: {exc}",
                    file_size=size,
                    content_hash=content_hash,
                )
            else:
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
    upload_session = await _get_upload_session_for_update(
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
