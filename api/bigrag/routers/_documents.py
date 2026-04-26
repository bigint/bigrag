from __future__ import annotations

import json
import uuid
from pathlib import Path

import sqlalchemy as sa
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import Collection, Document
from bigrag.logging import get_logger
from bigrag.models.document import DocumentResponse
from bigrag.services import metadata_schema, moderation
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage

logger = get_logger("bigrag.routers.documents")

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


def document_response(doc: Document, *, deduped: bool = False) -> DocumentResponse:
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


def parse_form_metadata(raw_metadata: str) -> dict:
    try:
        parsed = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def prepare_document_metadata(collection: dict, metadata: dict) -> dict:
    metadata_schema.validate(metadata, collection.get("metadata_schema"))
    if collection.get("redact_pii"):
        return {**metadata, "_redact_pii": True}
    return metadata


async def moderate_upload_content(collection: dict, content: bytes) -> None:
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


async def read_upload_content(file: UploadFile, *, max_size: int) -> bytes:
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


async def persist_document(
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
    await recount_collection_documents(session, collection["id"])
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


def assert_collection_pin_matches(user: dict, *, collection_name: str) -> None:
    pinned = user.get("collection")
    if pinned and pinned != collection_name:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This API key is pinned to collection {pinned!r}; "
                f"request targeted {collection_name!r}."
            ),
        )


async def get_document_with_collection(
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


async def recount_collection_documents(
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
