from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.models.document import DocumentResponse
from bigrag.routers import enforce_collection_pin, ensure_embedding_or_400, get_collection_or_404
from bigrag.routers._documents import parse_form_metadata
from bigrag.routers.documents._router import router
from bigrag.routers.documents_uploads import (
    metadata_or_400,
    upload_extension_or_400,
    uuid_or_404,
    validated_upload_to_temp,
)
from bigrag.services import audit, collection_cache
from bigrag.services.document_progress import document_progress, publish_queued_progress
from bigrag.services.documents import (
    content_hash_match,
    document_response,
    get_document_payload,
    persist_document,
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.staged_files import StagedFileCleanupError, delete_staged_file_path
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.routers.documents")


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    collection_name: str,
    request: Request,
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    ensure_embedding_or_400(collection)
    logger.info("document upload", collection=collection_name, filename=file.filename)

    file_ext = upload_extension_or_400(file.filename)

    upload_limits = await get_values(["max_upload_size_mb"])
    max_upload_size_mb = upload_limits["max_upload_size_mb"]
    max_size = max_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {max_upload_size_mb}MB",
        )

    tmp_path, content_hash, file_size = await validated_upload_to_temp(
        file, file_ext, max_size=max_size
    )
    try:
        meta = metadata_or_400(
            collection, metadata, prepare_document_metadata, parse_form_metadata, user
        )

        existing = await session.scalar(content_hash_match(collection, content_hash, meta))
        if existing is not None:
            logger.info(
                "upload: dedup hit — returning existing doc",
                content_hash=content_hash[:12],
                doc_id=str(existing.id),
            )
            return document_response(
                existing,
                deduped=True,
                progress=await document_progress(existing, collection_name),
            )

        try:
            doc = await persist_document(
                session=session,
                collection_name=collection_name,
                collection=collection,
                filename=file.filename or "document",
                source=tmp_path,
                file_size=file_size,
                metadata=meta,
                content_hash=content_hash,
                raise_on_enqueue_failure=True,
            )
        except IntegrityError:
            existing = await session.scalar(content_hash_match(collection, content_hash, meta))
            if existing is not None:
                logger.info(
                    "upload: integrity dedup hit — returning existing doc",
                    content_hash=content_hash[:12],
                    doc_id=str(existing.id),
                )
                return document_response(
                    existing,
                    deduped=True,
                    progress=await document_progress(existing, collection_name),
                )
            raise
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass
    publish_queued_progress(doc, collection_name, "Queued for ingestion")

    audit.record(
        request,
        user=user,
        action="document.upload",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={
            "collection": collection_name,
            "filename": doc.filename,
            "size": doc.file_size,
        },
    )
    return document_response(doc, progress=await document_progress(doc, collection_name))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    collection_name: str,
    document_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
    return await get_document_payload(
        session,
        user=user,
        collection_name=collection_name,
        document_id=document_id,
    )


@router.delete("/{document_id}", response_model=StatusResponse)
async def delete_document(
    collection_name: str,
    document_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid_or_404(document_id, "Document"))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await ingestion_queue.cancel_documents([document_id])

    file_path = doc.file_path
    deleted_filename = doc.filename
    try:
        await delete_staged_file_path(file_path, raise_on_failure=True)
    except StagedFileCleanupError as exc:
        raise HTTPException(
            status_code=503,
            detail="Staged file cleanup failed. Try deleting the document again.",
        ) from exc
    await vector_store.delete_by_document(
        collection_name,
        document_id,
    )
    await session.delete(doc)
    await recount_collection_documents(session, collection["id"])
    await session.commit()
    await collection_cache.invalidate(collection_name)
    await invalidate_collection_query_cache(collection_name)

    await enqueue_webhook_event(
        "document.deleted",
        collection=collection_name,
        data={
            "document_id": document_id,
            "collection": collection_name,
            "filename": deleted_filename,
        },
    )
    audit.record(
        request,
        user=user,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        metadata={"collection": collection_name, "filename": deleted_filename},
    )
    return StatusResponse(status="ok", message="Document deleted")
