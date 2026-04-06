from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from bigrag.config import settings
from bigrag.database import db
from bigrag.middleware.auth import get_current_user
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
from bigrag.services.queue import IngestionJob, event_bus, ingestion_queue
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = logging.getLogger("bigrag.routers.documents")

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


def _row_to_response(row: dict) -> DocumentResponse:
    r = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            r[k] = str(v)
        else:
            r[k] = v
    return DocumentResponse(**r)


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    collection_name: str,
    request: Request,
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    content = b"".join(chunks)

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    doc_id = str(uuid.uuid4())
    file_ext = Path(file.filename or "document").suffix
    storage_key = f"{collection_name}/{doc_id}{file_ext}"

    storage = get_storage()
    await storage.put(storage_key, content)
    logger.info(f"upload: stored key={storage_key} size={len(content)}")

    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        meta = {}

    try:
        row = await db.fetchrow(
            """
            INSERT INTO documents
                (id, collection_id, filename, file_type, file_size, file_path, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.UUID(doc_id),
            collection["id"],
            file.filename or "document",
            file_ext.lstrip("."),
            len(content),
            storage_key,
            meta,
        )
    except Exception:
        await storage.delete(storage_key)
        raise

    await ingestion_queue.enqueue(
        IngestionJob(
            document_id=doc_id,
            file_path=storage_key,
            collection_name=collection_name,
            embedding_provider=collection["embedding_provider"],
            embedding_model=collection["embedding_model"],
            embedding_dimension=collection["dimension"],
            embedding_api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
            chunk_size=collection["chunk_size"],
            chunk_overlap=collection["chunk_overlap"],
        )
    )

    return _row_to_response(dict(row))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_name: str,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    if status:
        rows = await db.fetch(
            """
            SELECT * FROM documents
            WHERE collection_id = $1 AND status = $2
            ORDER BY created_at DESC LIMIT $3 OFFSET $4
            """,
            collection["id"],
            status,
            limit,
            offset,
        )
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM documents WHERE collection_id = $1 AND status = $2",
            collection["id"],
            status,
        )
    else:
        rows = await db.fetch(
            """
            SELECT * FROM documents
            WHERE collection_id = $1
            ORDER BY created_at DESC LIMIT $2 OFFSET $3
            """,
            collection["id"],
            limit,
            offset,
        )
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM documents WHERE collection_id = $1",
            collection["id"],
        )

    return DocumentListResponse(
        documents=[_row_to_response(dict(r)) for r in rows],
        total=count_row["cnt"],
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return _row_to_response(dict(row))


@router.delete("/{document_id}")
async def delete_document(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    await vector_store.delete_by_document(collection_name, document_id)

    await db.execute("DELETE FROM documents WHERE id = $1", uuid.UUID(document_id))

    await db.execute(
        """
        UPDATE collections SET
            document_count = (
                SELECT COUNT(*) FROM documents WHERE collection_id = $1 AND status = 'ready'
            ),
            updated_at = now()
        WHERE id = $1
        """,
        collection["id"],
    )

    await get_storage().delete(row["file_path"])

    return {"status": "ok", "message": "Document deleted"}


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not await get_storage().exists(row["file_path"]):
        raise HTTPException(
            status_code=400,
            detail="Source file no longer exists. Upload the document again.",
        )

    await vector_store.delete_by_document(collection_name, document_id)

    await db.execute(
        "UPDATE documents SET status = 'pending', chunk_count = 0, "
        "error_message = NULL, updated_at = now() WHERE id = $1",
        uuid.UUID(document_id),
    )

    await ingestion_queue.enqueue(
        IngestionJob(
            document_id=document_id,
            file_path=row["file_path"],
            collection_name=collection_name,
            embedding_provider=collection["embedding_provider"],
            embedding_model=collection["embedding_model"],
            embedding_dimension=collection["dimension"],
            embedding_api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
            chunk_size=collection["chunk_size"],
            chunk_overlap=collection["chunk_overlap"],
        )
    )

    return {"status": "ok", "message": "Document reprocessing started"}


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = await vector_store.get_chunks(collection_name, document_id)
    return {"chunks": chunks, "total": len(chunks)}


@router.get("/{document_id}/file")
async def download_document_file(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    storage = get_storage()
    if not await storage.exists(row["file_path"]):
        raise HTTPException(status_code=404, detail="File not found in storage")

    data = await storage.get(row["file_path"])

    content_type_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "html": "text/html",
        "htm": "text/html",
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
    ext = row["file_type"].lower()
    content_type = content_type_map.get(ext, "application/octet-stream")

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{row["filename"]}"'},
    )


@router.post("/batch/upload", response_model=DocumentListResponse, status_code=201)
async def batch_upload_documents(
    collection_name: str,
    request: Request,
    files: list[UploadFile] = File(...),
    metadata: str = Form(default="{}"),
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    try:
        get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(files) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 files per batch upload")

    try:
        shared_meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        shared_meta = {}

    max_size = settings.max_upload_size_mb * 1024 * 1024

    # Pre-validate and read all files before committing any
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
                    detail=(
                        f"File '{file.filename}' too large. "
                        f"Max size: {settings.max_upload_size_mb}MB"
                    ),
                )
            chunks.append(chunk)
        content = b"".join(chunks)
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' is empty",
            )
        validated.append((file, content))

    results = []
    for file, content in validated:
        doc_id = str(uuid.uuid4())
        ext = Path(file.filename or "document").suffix
        storage_key = f"{collection_name}/{doc_id}{ext}"

        storage = get_storage()
        await storage.put(storage_key, content)

        row = await db.fetchrow(
            """
            INSERT INTO documents
                (id, collection_id, filename, file_type, file_size, file_path, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.UUID(doc_id),
            collection["id"],
            file.filename or "document",
            ext.lstrip("."),
            len(content),
            storage_key,
            shared_meta,
        )

        await ingestion_queue.enqueue(
            IngestionJob(
                document_id=doc_id,
                file_path=storage_key,
                collection_name=collection_name,
                embedding_provider=collection["embedding_provider"],
                embedding_model=collection["embedding_model"],
                embedding_dimension=collection["dimension"],
                embedding_api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
                chunk_size=collection["chunk_size"],
                chunk_overlap=collection["chunk_overlap"],
            )
        )
        results.append(_row_to_response(dict(row)))

    logger.info(f"batch_upload: collection={collection_name} files={len(results)}")
    return DocumentListResponse(documents=results, total=len(results))


@router.post("/batch/status", response_model=BatchStatusResponse)
async def batch_get_status(
    collection_name: str,
    body: BatchStatusRequest,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch status")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    placeholders = ", ".join(f"${i + 2}" for i in range(len(uuids)))
    rows = await db.fetch(
        f"SELECT id, status, error_message, chunk_count FROM documents "
        f"WHERE collection_id = $1 AND id IN ({placeholders})",
        collection["id"],
        *uuids,
    )

    documents = [
        DocumentStatusResponse(
            id=str(r["id"]),
            status=r["status"],
            error_message=r["error_message"],
            chunk_count=r["chunk_count"],
        )
        for r in rows
    ]

    return BatchStatusResponse(documents=documents, total=len(documents))


@router.post("/batch/get", response_model=BatchGetResponse)
async def batch_get_documents(
    collection_name: str,
    body: BatchGetRequest,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch get")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    placeholders = ", ".join(f"${i + 2}" for i in range(len(uuids)))
    rows = await db.fetch(
        f"SELECT * FROM documents WHERE collection_id = $1 AND id IN ({placeholders})",
        collection["id"],
        *uuids,
    )

    documents = [_row_to_response(dict(r)) for r in rows]
    logger.info(
        f"batch_get: collection={collection_name} requested={len(uuids)} found={len(documents)}"
    )
    return BatchGetResponse(documents=documents, total=len(documents))


@router.post("/batch/delete", response_model=BatchDeleteResponse)
async def batch_delete_documents(
    collection_name: str,
    body: BatchDeleteRequest,
    _: dict = Depends(get_current_user),
):
    import asyncio

    collection = await get_collection_or_404(collection_name)

    if len(body.document_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per batch delete")

    uuids = [uuid.UUID(d) for d in body.document_ids]
    placeholders = ", ".join(f"${i + 2}" for i in range(len(uuids)))
    rows = await db.fetch(
        f"SELECT * FROM documents WHERE collection_id = $1 AND id IN ({placeholders})",
        collection["id"],
        *uuids,
    )
    rows_by_id = {str(r["id"]): r for r in rows}

    errors = []
    not_found = [
        {"document_id": d, "error": "Document not found"}
        for d in body.document_ids
        if d not in rows_by_id
    ]
    errors.extend(not_found)

    async def _delete_one(doc_id: str, row: dict) -> bool:
        try:
            await asyncio.gather(
                vector_store.delete_by_document(collection_name, doc_id),
                db.execute("DELETE FROM documents WHERE id = $1", uuid.UUID(doc_id)),
                get_storage().delete(row["file_path"]),
            )
            return True
        except Exception as e:
            logger.error(f"batch_delete: failed to delete doc={doc_id}: {e!r}")
            errors.append({"document_id": doc_id, "error": str(e)})
            return False

    results = await asyncio.gather(
        *[_delete_one(doc_id, row) for doc_id, row in rows_by_id.items()]
    )
    deleted = sum(1 for r in results if r)

    await db.execute(
        """
        UPDATE collections SET
            document_count = (
                SELECT COUNT(*) FROM documents WHERE collection_id = $1 AND status = 'ready'
            ),
            updated_at = now()
        WHERE id = $1
        """,
        collection["id"],
    )

    logger.info(
        f"batch_delete: collection={collection_name} deleted={deleted} errors={len(errors)}"
    )
    return BatchDeleteResponse(status="ok", deleted=deleted, errors=errors)


@router.get("/{document_id}/progress")
async def document_progress_sse(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    import asyncio

    async def generate():
        yield (
            'data: {"step":"connected","status":"connected",'
            '"message":"Listening for progress","progress":0}\n\n'
        )
        try:
            async with asyncio.timeout(600):  # 10 min max
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
