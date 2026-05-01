from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
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
    DocumentResponse,
    DocumentStatusResponse,
)
from bigrag.routers import get_collection_or_404, get_embedding_model_for
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    assert_collection_pin_matches,
    document_response,
    get_document_with_collection,
    parse_form_metadata,
    persist_document,
    prepare_document_metadata,
    read_upload_content,
    recount_collection_documents,
)
from bigrag.services import audit, semantic_cache
from bigrag.services.event_bus import event_bus
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.documents")

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])


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
        return document_response(existing, deduped=True)

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
    await semantic_cache.invalidate(collection_name)

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
    return document_response(doc)


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
        documents=[document_response(d) for d in docs],
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
    return document_response(doc)


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

    await get_storage().delete(file_path)
    await semantic_cache.invalidate(collection_name)

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
    await semantic_cache.invalidate(collection_name)

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
        shared_meta = prepare_document_metadata(collection, parse_form_metadata(metadata))
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
            content = await read_upload_content(file, max_size=max_size)
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
            created.append(document_response(existing, deduped=True))
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
        seen_by_hash[content_hash] = doc
        created.append(document_response(doc))

    logger.info(f"batch_upload: collection={collection_name} files={len(created)}")
    await semantic_cache.invalidate(collection_name)
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

    documents = [document_response(d) for d in docs]
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
    if deleted:
        await semantic_cache.invalidate(collection_name)

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
    return document_response(doc)


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


def _parse_progress_document_ids(raw_ids: list[str]) -> tuple[list[str], list[uuid.UUID]]:
    seen: set[str] = set()
    doc_ids: list[str] = []
    doc_uuids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            parsed = uuid.UUID(raw_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid document ID: {raw_id}") from exc
        normalized = str(parsed)
        if normalized in seen:
            continue
        seen.add(normalized)
        doc_ids.append(normalized)
        doc_uuids.append(parsed)
    return doc_ids, doc_uuids


async def _ensure_documents_in_collection(
    session: AsyncSession,
    collection_id: uuid.UUID,
    doc_uuids: list[uuid.UUID],
) -> None:
    found = set(
        await session.scalars(
            sa.select(Document.id)
            .where(Document.collection_id == collection_id)
            .where(Document.id.in_(doc_uuids))
        )
    )
    if len(found) != len(doc_uuids):
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/batch/progress")
async def batch_progress_sse(
    collection_name: str,
    ids: str = Query(..., description="Comma-separated document IDs"),
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    import orjson

    raw_doc_ids = [d.strip() for d in ids.split(",") if d.strip()]
    if not raw_doc_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")
    if len(raw_doc_ids) > 100:
        raise HTTPException(status_code=400, detail="Max 100 document IDs per stream")
    collection = await get_collection_or_404(collection_name)
    assert_collection_pin_matches(user, collection_name=collection_name)
    doc_ids, doc_uuids = _parse_progress_document_ids(raw_doc_ids)
    await _ensure_documents_in_collection(session, collection["id"], doc_uuids)

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

        queues = {doc_id: event_bus.subscribe(doc_id) for doc_id in doc_ids}
        pending = {asyncio.create_task(q.get()): doc_id for doc_id, q in queues.items()}
        try:
            async with asyncio.timeout(600):
                while len(completed_set) < len(doc_ids) and pending:
                    done_tasks, _ = await asyncio.wait(
                        pending,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done_tasks:
                        event_doc_id = pending.pop(task)
                        event = task.result()
                        if event is None:
                            progress_map[event_doc_id] = {
                                "progress": 1.0,
                                "status": "complete",
                                "step": "complete",
                                "message": "Complete",
                            }
                            completed_set.add(event_doc_id)
                            document_id = event_doc_id
                            document_status = "complete"
                            document_step = "complete"
                            document_progress = 1.0
                        else:
                            progress_map[event_doc_id] = {
                                "progress": event.progress,
                                "status": event.status,
                                "step": event.step,
                                "message": event.message,
                            }
                            document_id = event.document_id
                            document_status = event.status
                            document_step = event.step
                            document_progress = event.progress

                            if event.status not in ("complete", "failed"):
                                pending[asyncio.create_task(queues[event_doc_id].get())] = (
                                    event_doc_id
                                )

                        if document_status in ("complete", "failed"):
                            completed_set.add(event_doc_id)

                        done = len(completed_set)
                        failed = sum(1 for d in progress_map.values() if d["status"] == "failed")
                        avg_progress = sum(d["progress"] for d in progress_map.values()) / len(
                            doc_ids
                        )

                        summary = {
                            "step": "batch_progress",
                            "status": "complete" if done == len(doc_ids) else "processing",
                            "message": f"{done}/{len(doc_ids)} documents done",
                            "progress": round(avg_progress, 3),
                            "total": len(doc_ids),
                            "completed": done - failed,
                            "failed": failed,
                            "document_id": document_id,
                            "document_status": document_status,
                            "document_step": document_step,
                            "document_progress": document_progress,
                        }
                        yield f"data: {orjson.dumps(summary).decode()}\n\n"
        except TimeoutError:
            yield (
                'data: {"step":"timeout","status":"timeout",'
                '"message":"Stream timed out after 10 minutes","progress":0}\n\n'
            )
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for doc_id, q in queues.items():
                event_bus.unsubscribe(doc_id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{document_id}/progress")
async def document_progress_sse(
    collection_name: str,
    document_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)
    assert_collection_pin_matches(user, collection_name=collection_name)
    doc_ids, doc_uuids = _parse_progress_document_ids([document_id])
    await _ensure_documents_in_collection(session, collection["id"], doc_uuids)
    document_id = doc_ids[0]

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
