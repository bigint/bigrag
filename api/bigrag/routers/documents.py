from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.common import StatusResponse
from bigrag.models.document import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchGetRequest,
    BatchGetResponse,
    BatchStatusRequest,
    BatchStatusResponse,
    DocumentListResponse,
    DocumentProgressResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from bigrag.routers import get_collection_or_404, get_embedding_model_for
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    UploadBudget,
    assert_collection_pin_matches,
    content_hash_match,
    document_progress_response,
    document_response,
    get_document_with_collection,
    parse_form_metadata,
    persist_document,
    prepare_document_metadata,
    read_upload_content,
    recount_collection_documents,
)
from bigrag.services import audit, collection_cache
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.documents")

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])

TERMINAL_DOCUMENT_STATUSES = {"ready", "failed"}
TERMINAL_PROGRESS_STATUSES = {"complete", "failed"}


def _fallback_progress(doc: Document, collection_name: str) -> DocumentProgressResponse:
    doc_id = str(doc.id)
    if doc.status == "ready":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="complete",
            status="complete",
            message=f"Ready — {doc.chunk_count} chunks",
            progress=1.0,
            detail={"chunks": doc.chunk_count},
        )
    if doc.status == "failed":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="failed",
            status="failed",
            message=doc.error_message or "Ingestion failed",
            progress=0.0,
        )
    if doc.status == "processing":
        return document_progress_response(
            document_id=doc_id,
            collection_name=collection_name,
            step="processing",
            status="processing",
            message="Processing document",
            progress=0.05,
        )
    return document_progress_response(
        document_id=doc_id,
        collection_name=collection_name,
        step="queued",
        status="pending",
        message="Queued for ingestion",
        progress=0.0,
    )


async def _document_progress(doc: Document, collection_name: str) -> DocumentProgressResponse:
    event = await event_bus.latest(str(doc.id))
    if event is None or (
        doc.status in TERMINAL_DOCUMENT_STATUSES and event.status not in TERMINAL_PROGRESS_STATUSES
    ):
        return _fallback_progress(doc, collection_name)
    return document_progress_response(
        document_id=event.document_id,
        collection_name=event.collection_name or collection_name,
        step=event.step,
        status=event.status,
        message=event.message,
        progress=event.progress,
        detail=event.detail,
    )


def _publish_queued_progress(doc: Document, collection_name: str, message: str) -> None:
    event_bus.publish(
        IngestionEvent(
            document_id=str(doc.id),
            collection_name=collection_name,
            step="queued",
            status="pending",
            message=message,
            progress=0.0,
        )
    )


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
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    logger.info(f"upload: collection={collection_name} file={file.filename}")

    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext and file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file_ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    upload_limits = await get_values(["max_upload_size_mb"])
    max_upload_size_mb = upload_limits["max_upload_size_mb"]
    max_size = max_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {max_upload_size_mb}MB",
        )

    content = await read_upload_content(file, max_size=max_size)

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        validate_upload(content, file_ext)
    except InvalidFileContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        meta = prepare_document_metadata(collection, parse_form_metadata(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc

    content_hash = hashlib.sha256(content).hexdigest()
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
            progress=await _document_progress(existing, collection_name),
        )

    doc = await persist_document(
        session=session,
        collection_name=collection_name,
        collection=collection,
        filename=file.filename or "document",
        content=content,
        metadata=meta,
        content_hash=content_hash,
        raise_on_enqueue_failure=True,
    )
    _publish_queued_progress(doc, collection_name, "Queued for ingestion")

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
    return document_response(doc, progress=await _document_progress(doc, collection_name))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_name: str,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    stmt = (
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .order_by(Document.created_at.desc())
    )
    count_stmt = (
        sa.select(sa.func.count())
        .select_from(Document)
        .where(Document.collection_id == collection["id"])
    )
    if status:
        stmt = stmt.where(Document.status == status)
        count_stmt = count_stmt.where(Document.status == status)

    docs = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    total = await session.scalar(count_stmt)

    documents = []
    for doc in docs:
        documents.append(
            document_response(doc, progress=await _document_progress(doc, collection_name))
        )

    return DocumentListResponse(documents=documents, total=total or 0)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid.UUID(document_id))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document_response(doc, progress=await _document_progress(doc, collection_name))


@router.delete("/{document_id}", response_model=StatusResponse)
async def delete_document(
    collection_name: str,
    document_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid.UUID(document_id))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await ingestion_queue.cancel_documents([document_id])
    await vector_store.delete_by_document(collection_name, document_id)

    file_path = doc.file_path
    deleted_filename = doc.filename
    await session.delete(doc)
    await recount_collection_documents(session, collection["id"])
    await session.commit()
    await collection_cache.invalidate(collection_name)
    await invalidate_collection_query_cache(collection_name)

    await get_storage().delete(file_path)

    audit.record(
        request,
        user=user,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        metadata={"collection": collection_name, "filename": deleted_filename},
    )
    return StatusResponse(status="ok", message="Document deleted")


@router.post("/{document_id}/reprocess", response_model=StatusResponse)
async def reprocess_document(
    collection_name: str,
    document_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid.UUID(document_id))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not await get_storage().exists(doc.file_path):
        raise HTTPException(
            status_code=400,
            detail="Source file no longer exists. Upload the document again.",
        )

    await ingestion_queue.cancel_documents([document_id])
    await vector_store.delete_by_document(collection_name, document_id)

    doc.status = "pending"
    doc.chunk_count = 0
    doc.error_message = None
    await session.commit()
    _publish_queued_progress(doc, collection_name, "Queued for reprocessing")

    await ingestion_queue.enqueue(
        create_ingestion_job(
            document_id=document_id,
            file_path=doc.file_path,
            collection_name=collection_name,
            collection=collection,
        )
    )

    audit.record(
        request,
        user=user,
        action="document.reprocess",
        resource_type="document",
        resource_id=document_id,
        metadata={"collection": collection_name, "filename": doc.filename},
    )
    return StatusResponse(status="ok", message="Document reprocessing started")


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    collection_name: str,
    document_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    exists = await session.scalar(
        sa.select(Document.id)
        .where(Document.id == uuid.UUID(document_id))
        .where(Document.collection_id == collection["id"])
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks, total = await vector_store.get_chunks(
        collection_name,
        document_id,
        limit=limit,
        offset=offset,
    )
    return {"chunks": chunks, "total": total}


@router.get("/{document_id}/file")
async def download_document_file(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    doc = await session.scalar(
        sa.select(Document)
        .where(Document.id == uuid.UUID(document_id))
        .where(Document.collection_id == collection["id"])
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    storage = get_storage()
    if not await storage.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found in storage")

    data = await storage.get(doc.file_path)

    content_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "html": "application/octet-stream",
        "htm": "application/octet-stream",
        "md": "text/markdown",
        "txt": "text/plain",
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "xml": "application/xml",
        "json": "application/json",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "tiff": "image/tiff",
        "bmp": "image/bmp",
    }
    ext = doc.file_type.lower()
    content_type = content_type_map.get(ext, "application/octet-stream")

    from urllib.parse import quote

    safe_ascii = re.sub(r"[\x00-\x1f\x7f\"\\]", "_", doc.filename)
    encoded = quote(doc.filename, safe="")
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded}"
            )
        },
    )


@router.post("/batch/upload", response_model=DocumentListResponse, status_code=201)
async def batch_upload_documents(
    collection_name: str,
    request: Request,
    files: list[UploadFile] = File(...),
    metadata: str = Form(default="{}"),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if len(files) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files per batch upload")

    upload_limits = await get_values(["max_upload_size_mb", "max_batch_upload_size_mb"])
    max_upload_size_mb = upload_limits["max_upload_size_mb"]
    max_batch_upload_size_mb = upload_limits["max_batch_upload_size_mb"]
    max_size = max_upload_size_mb * 1024 * 1024
    batch_max_size = max_batch_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > batch_max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Batch upload too large. Max size: {max_batch_upload_size_mb}MB",
        )
    budget = UploadBudget(batch_max_size)
    try:
        shared_meta = prepare_document_metadata(collection, parse_form_metadata(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc

    created: list[DocumentResponse] = []
    seen_by_hash: dict[str, Document] = {}
    for file in files:
        file_ext = Path(file.filename or "").suffix.lower()
        if file_ext and file_ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type '{file_ext}' for file '{file.filename}'. "
                    f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
                ),
            )

        try:
            content = await read_upload_content(file, max_size=max_size, budget=budget)
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"File '{file.filename}': {exc.detail}",
            ) from exc
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is empty",
            )
        try:
            validate_upload(content, file_ext)
        except InvalidFileContentError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}': {exc}",
            ) from exc
        content_hash = hashlib.sha256(content).hexdigest()
        existing = seen_by_hash.get(content_hash)
        if existing is None:
            existing = await session.scalar(
                content_hash_match(collection, content_hash, shared_meta)
            )
            if existing is not None:
                seen_by_hash[content_hash] = existing
        if existing is not None:
            created.append(
                document_response(
                    existing,
                    deduped=True,
                    progress=await _document_progress(existing, collection_name),
                )
            )
            continue

        doc = await persist_document(
            session=session,
            collection_name=collection_name,
            collection=collection,
            filename=file.filename or "document",
            content=content,
            metadata=shared_meta,
            content_hash=content_hash,
            raise_on_enqueue_failure=False,
        )
        _publish_queued_progress(doc, collection_name, "Queued for ingestion")
        seen_by_hash[content_hash] = doc
        created.append(
            document_response(doc, progress=await _document_progress(doc, collection_name))
        )

    logger.info(f"batch_upload: collection={collection_name} files={len(created)}")
    audit.record(
        request,
        user=user,
        action="document.batch_upload",
        resource_type="collection",
        resource_id=str(collection["id"]),
        metadata={"collection": collection_name, "files": len(created)},
    )
    return DocumentListResponse(
        documents=created,
        total=len(created),
    )


@router.post("/batch/status", response_model=BatchStatusResponse)
async def batch_get_status(
    collection_name: str,
    body: BatchStatusRequest,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch status")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()

    documents = []
    for doc in docs:
        documents.append(
            DocumentStatusResponse(
                id=str(doc.id),
                status=doc.status,
                error_message=doc.error_message,
                chunk_count=doc.chunk_count,
                progress=await _document_progress(doc, collection_name),
            )
        )

    return BatchStatusResponse(documents=documents, total=len(documents))


@router.post("/batch/get", response_model=BatchGetResponse)
async def batch_get_documents(
    collection_name: str,
    body: BatchGetRequest,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch get")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()

    documents = [
        document_response(d, progress=await _document_progress(d, collection_name)) for d in docs
    ]
    logger.info(
        f"batch_get: collection={collection_name} requested={len(uuids)} found={len(documents)}"
    )
    return BatchGetResponse(documents=documents, total=len(documents))


@router.post("/batch/delete", response_model=BatchDeleteResponse)
async def batch_delete_documents(
    collection_name: str,
    body: BatchDeleteRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch delete")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()
    by_id = {str(d.id): d for d in docs}

    errors = [
        {"document_id": d, "error": "Document not found"}
        for d in body.document_ids
        if d not in by_id
    ]

    async def _delete_one(doc_id: str, doc: Document) -> bool:
        try:
            await vector_store.delete_by_document(collection_name, doc_id)
            await get_storage().delete(doc.file_path)
            return True
        except Exception as e:
            logger.error(f"batch_delete: failed to delete doc={doc_id}: {e!r}")
            errors.append({"document_id": doc_id, "error": str(e)})
            return False

    await ingestion_queue.cancel_documents(list(by_id))
    results = await asyncio.gather(*[_delete_one(doc_id, doc) for doc_id, doc in by_id.items()])
    deleted = sum(1 for r in results if r)

    deleted_ids = [uuid.UUID(d) for d, ok in zip(by_id.keys(), results, strict=True) if ok]
    if deleted_ids:
        await session.execute(sa.delete(Document).where(Document.id.in_(deleted_ids)))
    await recount_collection_documents(session, collection["id"])
    await session.commit()
    await collection_cache.invalidate(collection_name)
    await invalidate_collection_query_cache(collection_name)

    logger.info(
        f"batch_delete: collection={collection_name} deleted={deleted} errors={len(errors)}"
    )
    audit.record(
        request,
        user=user,
        action="document.batch_delete",
        resource_type="collection",
        resource_id=str(collection["id"]),
        metadata={"collection": collection_name, "deleted": deleted, "errors": len(errors)},
    )
    return BatchDeleteResponse(status="ok", deleted=deleted, errors=errors)


global_router = APIRouter(prefix="/v1/documents", tags=["documents"])


@global_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_global(
    document_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc, collection_name = await get_document_with_collection(session, document_id)
    assert_collection_pin_matches(user, collection_name=collection_name)
    return document_response(doc, progress=await _document_progress(doc, collection_name))


@global_router.get("/{document_id}/chunks")
async def get_document_chunks_global(
    document_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc, collection_name = await get_document_with_collection(session, document_id)
    assert_collection_pin_matches(user, collection_name=collection_name)
    chunks, total = await vector_store.get_chunks(
        collection_name,
        document_id,
        limit=limit,
        offset=offset,
    )
    return {"chunks": chunks, "total": total}
