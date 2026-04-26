from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import Collection, Document
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
    DocumentResponse,
    DocumentStatusResponse,
)
from bigrag.models.s3 import S3IngestRequest, S3IngestResponse
from bigrag.routers import get_collection_or_404, get_embedding_model_for
from bigrag.services import audit, metadata_schema, moderation
from bigrag.services.event_bus import event_bus
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.documents")

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".md",
    ".txt",
    ".csv",
    ".tsv",
    ".xml",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
    ".gif",
}


def _document_response(doc: Document, *, deduped: bool = False) -> DocumentResponse:
    return DocumentResponse(
        id=str(doc.id),
        collection_id=str(doc.collection_id),
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status,
        error_message=doc.error_message,
        metadata=doc.meta or {},
        content_hash=doc.content_hash,
        deduped=deduped,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _parse_form_metadata(raw_metadata: str) -> dict:
    try:
        parsed = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _prepare_document_metadata(collection: dict, metadata: dict) -> dict:
    metadata_schema.validate(metadata, collection.get("metadata_schema"))
    if collection.get("redact_pii"):
        return {**metadata, "_redact_pii": True}
    return metadata


async def _moderate_upload_content(collection: dict, content: bytes) -> None:
    if not collection.get("moderation_enabled"):
        return
    text_preview = content[:50_000].decode("utf-8", errors="ignore")
    if not text_preview.strip():
        return
    flagged, reason = await moderation.check_text(
        text_preview, collection.get("embedding_api_key") or settings.embedding_api_key
    )
    if flagged:
        raise HTTPException(status_code=400, detail=f"Upload blocked: {reason}")


async def _read_upload_content(file: UploadFile, *, max_size: int) -> bytes:
    chunks = []
    total_size = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


async def _persist_document(
    *,
    session: AsyncSession,
    collection_name: str,
    collection: dict,
    filename: str,
    content: bytes,
    metadata: dict,
    content_hash: str,
    raise_on_enqueue_failure: bool,
) -> Document:
    doc_id = uuid.uuid4()
    file_ext = Path(filename or "document").suffix
    storage_key = f"{collection_name}/{doc_id}{file_ext}"
    storage = get_storage()

    await storage.put(storage_key, content)
    logger.info(f"upload: stored key={storage_key} size={len(content)}")

    doc = Document(
        id=doc_id,
        collection_id=collection["id"],
        filename=filename or "document",
        file_type=file_ext.lstrip("."),
        file_size=len(content),
        file_path=storage_key,
        content_hash=content_hash,
        meta=dict(metadata),
    )
    session.add(doc)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await storage.delete(storage_key)
        raise
    await session.refresh(doc)
    await _recount_collection_documents(session, collection["id"])
    await session.commit()

    try:
        await ingestion_queue.enqueue(
            create_ingestion_job(
                document_id=str(doc_id),
                file_path=storage_key,
                collection_name=collection_name,
                collection=collection,
                fallback_api_key=settings.embedding_api_key,
            )
        )
    except Exception as exc:
        logger.exception(
            "upload: enqueue failed, marking document failed",
            doc_id=str(doc_id),
            collection=collection_name,
        )
        doc.status = "failed"
        doc.error_message = f"enqueue failed: {exc.__class__.__name__}: {exc}"
        await session.commit()
        await session.refresh(doc)
        if raise_on_enqueue_failure:
            raise HTTPException(
                status_code=503,
                detail=("Ingestion queue unavailable — document saved as failed, retry later."),
            ) from exc

    return doc


def _assert_collection_pin_matches(user: dict, *, collection_name: str) -> None:
    pinned = user.get("collection")
    if pinned and pinned != collection_name:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This API key is pinned to collection {pinned!r}; "
                f"request targeted {collection_name!r}."
            ),
        )


async def _get_document_with_collection(
    session: AsyncSession,
    document_id: str,
) -> tuple[Document, str]:
    row = (
        await session.execute(
            sa.select(Document, Collection.name)
            .join(Collection, Collection.id == Document.collection_id)
            .where(Document.id == uuid.UUID(document_id))
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, collection_name = row
    return doc, collection_name


async def _recount_collection_documents(
    session: AsyncSession,
    collection_id: uuid.UUID,
) -> None:

    subq = (
        sa.select(sa.func.count())
        .select_from(Document)
        .where(Document.collection_id == collection_id)
        .scalar_subquery()
    )
    await session.execute(
        sa.update(Collection).where(Collection.id == collection_id).values(document_count=subq)
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

    max_size = settings.max_upload_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    content = await _read_upload_content(file, max_size=max_size)

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        validate_upload(content, file_ext)
    except InvalidFileContentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        meta = _prepare_document_metadata(collection, _parse_form_metadata(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc

    await _moderate_upload_content(collection, content)

    content_hash = hashlib.sha256(content).hexdigest()
    existing = await session.scalar(
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .where(Document.content_hash == content_hash)
        .limit(1)
    )
    if existing is not None:
        logger.info(
            "upload: dedup hit — returning existing doc",
            content_hash=content_hash[:12],
            doc_id=str(existing.id),
        )
        return _document_response(existing, deduped=True)

    doc = await _persist_document(
        session=session,
        collection_name=collection_name,
        collection=collection,
        filename=file.filename or "document",
        content=content,
        metadata=meta,
        content_hash=content_hash,
        raise_on_enqueue_failure=True,
    )

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
    return _document_response(doc)


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

    return DocumentListResponse(
        documents=[_document_response(d) for d in docs],
        total=total or 0,
    )


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
    return _document_response(doc)


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

    await vector_store.delete_by_document(collection_name, document_id)

    file_path = doc.file_path
    deleted_filename = doc.filename
    await session.delete(doc)
    await _recount_collection_documents(session, collection["id"])
    await session.commit()

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

    await vector_store.delete_by_document(collection_name, document_id)

    doc.status = "pending"
    doc.chunk_count = 0
    doc.error_message = None
    await session.commit()

    await ingestion_queue.enqueue(
        create_ingestion_job(
            document_id=document_id,
            file_path=doc.file_path,
            collection_name=collection_name,
            collection=collection,
            fallback_api_key=settings.embedding_api_key,
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

    max_size = settings.max_upload_size_mb * 1024 * 1024
    try:
        shared_meta = _prepare_document_metadata(collection, _parse_form_metadata(metadata))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"metadata: {exc}") from exc

    validated: list[tuple[UploadFile, bytes]] = []
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
            content = await _read_upload_content(file, max_size=max_size)
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=(
                    f"File '{file.filename}' too large. Max size: {settings.max_upload_size_mb}MB"
                ),
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
        await _moderate_upload_content(collection, content)
        validated.append((file, content))

    created: list[DocumentResponse] = []
    seen_by_hash: dict[str, Document] = {}
    for file, content in validated:
        content_hash = hashlib.sha256(content).hexdigest()
        existing = seen_by_hash.get(content_hash)
        if existing is None:
            existing = await session.scalar(
                sa.select(Document)
                .where(Document.collection_id == collection["id"])
                .where(Document.content_hash == content_hash)
                .limit(1)
            )
            if existing is not None:
                seen_by_hash[content_hash] = existing
        if existing is not None:
            created.append(_document_response(existing, deduped=True))
            continue

        doc = await _persist_document(
            session=session,
            collection_name=collection_name,
            collection=collection,
            filename=file.filename or "document",
            content=content,
            metadata=shared_meta,
            content_hash=content_hash,
            raise_on_enqueue_failure=False,
        )
        seen_by_hash[content_hash] = doc
        created.append(_document_response(doc))

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
    rows = (
        await session.execute(
            sa.select(Document.id, Document.status, Document.error_message, Document.chunk_count)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()

    documents = [
        DocumentStatusResponse(
            id=str(row.id),
            status=row.status,
            error_message=row.error_message,
            chunk_count=row.chunk_count,
        )
        for row in rows
    ]

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

    documents = [_document_response(d) for d in docs]
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

    results = await asyncio.gather(*[_delete_one(doc_id, doc) for doc_id, doc in by_id.items()])
    deleted = sum(1 for r in results if r)

    deleted_ids = [uuid.UUID(d) for d, ok in zip(by_id.keys(), results, strict=True) if ok]
    if deleted_ids:
        await session.execute(sa.delete(Document).where(Document.id.in_(deleted_ids)))
    await _recount_collection_documents(session, collection["id"])
    await session.commit()

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
    doc, collection_name = await _get_document_with_collection(session, document_id)
    _assert_collection_pin_matches(user, collection_name=collection_name)
    return _document_response(doc)


@global_router.get("/{document_id}/chunks")
async def get_document_chunks_global(
    document_id: str,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    doc, collection_name = await _get_document_with_collection(session, document_id)
    _assert_collection_pin_matches(user, collection_name=collection_name)
    chunks, total = await vector_store.get_chunks(
        collection_name,
        document_id,
        limit=limit,
        offset=offset,
    )
    return {"chunks": chunks, "total": total}


@router.post("/s3", response_model=S3IngestResponse, status_code=202)
async def ingest_from_s3(
    collection_name: str,
    body: S3IngestRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):

    from bigrag.services.s3_ingest import create_job

    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await create_job(
        collection_id=str(collection["id"]),
        collection_name=collection_name,
        bucket=body.bucket,
        prefix=body.prefix,
        region=body.region,
        endpoint_url=body.endpoint_url,
        access_key=body.access_key,
        secret_key=body.secret_key,
        no_sign_request=body.no_sign_request,
        metadata=body.metadata,
        file_types=body.file_types,
    )

    audit.record(
        request,
        user=user,
        action="document.s3_ingest",
        resource_type="collection",
        resource_id=str(collection["id"]),
        metadata={
            "collection": collection_name,
            "bucket": body.bucket,
            "prefix": body.prefix,
        },
    )
    return S3IngestResponse(
        status="accepted",
        message="S3 ingestion started in background",
    )


@router.get("/batch/progress")
async def batch_progress_sse(
    collection_name: str,
    ids: str = Query(..., description="Comma-separated document IDs"),
    _: dict = Depends(get_current_user),
):

    import orjson

    doc_ids = [d.strip() for d in ids.split(",") if d.strip()]
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")
    if len(doc_ids) > 100:
        raise HTTPException(status_code=400, detail="Max 100 document IDs per stream")

    async def generate():
        yield (
            f'data: {{"step":"connected","status":"connected",'
            f'"message":"Tracking {len(doc_ids)} documents","progress":0,'
            f'"total":{len(doc_ids)},"completed":0,"failed":0}}\n\n'
        )

        progress_map: dict[str, dict] = {
            d: {"progress": 0.0, "status": "pending", "step": "pending"} for d in doc_ids
        }
        completed_set: set[str] = set()

        q = event_bus.subscribe("*")
        try:
            async with asyncio.timeout(600):
                while len(completed_set) < len(doc_ids):
                    event = await q.get()
                    if event is None:
                        break
                    if event.document_id not in progress_map:
                        continue

                    progress_map[event.document_id] = {
                        "progress": event.progress,
                        "status": event.status,
                        "step": event.step,
                        "message": event.message,
                    }

                    if event.status in ("complete", "failed"):
                        completed_set.add(event.document_id)

                    done = len(completed_set)
                    failed = sum(1 for d in progress_map.values() if d["status"] == "failed")
                    avg_progress = sum(d["progress"] for d in progress_map.values()) / len(doc_ids)

                    summary = {
                        "step": "batch_progress",
                        "status": "complete" if done == len(doc_ids) else "processing",
                        "message": f"{done}/{len(doc_ids)} documents done",
                        "progress": round(avg_progress, 3),
                        "total": len(doc_ids),
                        "completed": done - failed,
                        "failed": failed,
                        "document_id": event.document_id,
                        "document_status": event.status,
                        "document_step": event.step,
                        "document_progress": event.progress,
                    }
                    yield f"data: {orjson.dumps(summary).decode()}\n\n"
        except TimeoutError:
            yield (
                'data: {"step":"timeout","status":"timeout",'
                '"message":"Stream timed out after 10 minutes","progress":0}\n\n'
            )
        finally:
            event_bus.unsubscribe("*", q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{document_id}/progress")
async def document_progress_sse(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):

    async def generate():
        yield (
            'data: {"step":"connected","status":"connected",'
            '"message":"Listening for progress","progress":0}\n\n'
        )
        try:
            async with asyncio.timeout(600):
                async for event in event_bus.stream(document_id):
                    yield event.to_sse()
        except TimeoutError:
            yield (
                'data: {"step":"timeout","status":"timeout",'
                '"message":"Stream timed out after 10 minutes","progress":0}\n\n'
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


from bigrag.services import pii  # noqa: E402, F401
