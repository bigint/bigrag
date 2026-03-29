from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from bigrag.config import settings
from bigrag.database import db
from bigrag.middleware.auth import get_current_user
from bigrag.models.document import DocumentListResponse, DocumentResponse
from bigrag.services.embedding import get_embedding_model
from bigrag.services.queue import IngestionJob, event_bus, ingestion_queue
from bigrag.services.vector_store import vector_store

router = APIRouter(prefix="/v1/collections/{collection_name}/documents", tags=["documents"])

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm",
    ".md", ".txt", ".csv", ".tsv", ".xml", ".json",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif",
}


def _row_to_response(row: dict) -> DocumentResponse:
    r = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            r[k] = str(v)
        else:
            r[k] = v
    return DocumentResponse(**r)


async def _get_collection(name: str) -> dict:
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    return dict(row)


def _validate_embedding_provider(collection: dict) -> None:
    """Validate the embedding provider is available before accepting the upload."""
    provider = collection["embedding_provider"]
    api_key = collection.get("embedding_api_key") or settings.embedding_api_key
    base_url = collection.get("embedding_base_url") or settings.embedding_base_url

    if provider in ("openai", "cohere", "custom") and not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Collection '{collection['name']}' uses '{provider}' embeddings but no API key is configured. "
                   f"Set BIGRAG_EMBEDDING_API_KEY or recreate the collection with an API key.",
        )

    try:
        get_embedding_model(
            provider=provider,
            model_name=collection["embedding_model"],
            dimension=collection["dimension"],
            api_key=api_key,
            base_url=base_url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    collection_name: str,
    file: UploadFile = File(...),
    metadata: str = Form(default="{}"),
    _: dict = Depends(get_current_user),
):
    collection = await _get_collection(collection_name)
    _validate_embedding_provider(collection)

    # Validate file type
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext and file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Validate file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    # Save file to disk
    upload_dir = Path(settings.upload_dir) / collection_name
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    file_ext = Path(file.filename or "document").suffix
    file_path = upload_dir / f"{doc_id}{file_ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    # Parse metadata
    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        meta = {}

    # Create document record
    try:
        row = await db.fetchrow(
            """
            INSERT INTO documents (id, collection_id, filename, file_type, file_size, file_path, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.UUID(doc_id), collection["id"], file.filename or "document",
            file_ext.lstrip("."), len(content), str(file_path), meta,
        )
    except Exception:
        # Clean up the file if DB insert fails
        file_path.unlink(missing_ok=True)
        raise

    # Enqueue for background processing
    await ingestion_queue.enqueue(IngestionJob(
        document_id=doc_id,
        file_path=str(file_path),
        collection_name=collection_name,
        embedding_provider=collection["embedding_provider"],
        embedding_model=collection["embedding_model"],
        embedding_dimension=collection["dimension"],
        embedding_api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
        embedding_base_url=collection.get("embedding_base_url") or settings.embedding_base_url,
        chunk_size=collection["chunk_size"],
        chunk_overlap=collection["chunk_overlap"],
    ))

    return _row_to_response(dict(row))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    collection_name: str,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    _: dict = Depends(get_current_user),
):
    collection = await _get_collection(collection_name)

    if status:
        rows = await db.fetch(
            """
            SELECT * FROM documents
            WHERE collection_id = $1 AND status = $2
            ORDER BY created_at DESC LIMIT $3 OFFSET $4
            """,
            collection["id"], status, limit, offset,
        )
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM documents WHERE collection_id = $1 AND status = $2",
            collection["id"], status,
        )
    else:
        rows = await db.fetch(
            """
            SELECT * FROM documents
            WHERE collection_id = $1
            ORDER BY created_at DESC LIMIT $2 OFFSET $3
            """,
            collection["id"], limit, offset,
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
    collection = await _get_collection(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id), collection["id"],
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
    collection = await _get_collection(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id), collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete vectors from Milvus
    await vector_store.delete_by_document(collection_name, document_id)

    # Delete file from disk
    file_path = Path(row["file_path"])
    if file_path.exists():
        file_path.unlink()

    # Delete from Postgres
    await db.execute("DELETE FROM documents WHERE id = $1", uuid.UUID(document_id))

    # Update collection count
    await db.execute(
        """
        UPDATE collections SET
            document_count = (SELECT COUNT(*) FROM documents WHERE collection_id = $1 AND status = 'ready'),
            updated_at = now()
        WHERE id = $1
        """,
        collection["id"],
    )

    return {"status": "ok", "message": "Document deleted"}


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await _get_collection(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM documents WHERE id = $1 AND collection_id = $2",
        uuid.UUID(document_id), collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    _validate_embedding_provider(collection)

    # Verify the source file still exists
    if not Path(row["file_path"]).exists():
        raise HTTPException(
            status_code=400,
            detail="Source file no longer exists on disk. Upload the document again.",
        )

    # Delete existing vectors
    await vector_store.delete_by_document(collection_name, document_id)

    # Reset status
    await db.execute(
        "UPDATE documents SET status = 'pending', chunk_count = 0, error_message = NULL, updated_at = now() WHERE id = $1",
        uuid.UUID(document_id),
    )

    # Enqueue for reprocessing
    await ingestion_queue.enqueue(IngestionJob(
        document_id=document_id,
        file_path=row["file_path"],
        collection_name=collection_name,
        embedding_provider=collection["embedding_provider"],
        embedding_model=collection["embedding_model"],
        embedding_dimension=collection["dimension"],
        embedding_api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
        embedding_base_url=collection.get("embedding_base_url") or settings.embedding_base_url,
        chunk_size=collection["chunk_size"],
        chunk_overlap=collection["chunk_overlap"],
    ))

    return {"status": "ok", "message": "Document reprocessing started"}


@router.get("/{document_id}/progress")
async def document_progress_sse(
    collection_name: str,
    document_id: str,
    _: dict = Depends(get_current_user),
):
    """SSE stream of real-time ingestion progress for a document."""

    async def generate():
        yield "data: {\"step\":\"connected\",\"status\":\"connected\",\"message\":\"Listening for progress\",\"progress\":0}\n\n"
        async for event in event_bus.stream(document_id):
            yield event.to_sse()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
