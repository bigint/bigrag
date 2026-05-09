from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.logging import get_logger
from bigrag.models.document import DocumentProgressResponse, DocumentResponse
from bigrag.services import collection_cache, metadata_schema
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import sync_value
from bigrag.services.storage import get_storage
from bigrag.services.tenant_enforcement import require_tenant_metadata, tenant_field

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


@dataclass
class UploadBudget:
    max_size: int
    used: int = 0

    def consume(self, size: int) -> None:
        self.used += size
        if self.used > self.max_size:
            max_mb = sync_value("max_batch_upload_size_mb")
            raise HTTPException(
                status_code=413,
                detail=f"Batch upload too large. Max size: {max_mb}MB",
            )


def document_progress_response(
    *,
    document_id: str,
    collection_name: str,
    step: str,
    status: str,
    message: str,
    progress: float,
    detail: dict | None = None,
) -> DocumentProgressResponse:
    return DocumentProgressResponse(
        document_id=document_id,
        collection_name=collection_name,
        step=step,
        status=status,
        message=message,
        progress=max(0.0, min(1.0, progress)),
        detail=detail or {},
    )


def document_response(
    doc: Document,
    *,
    deduped: bool = False,
    progress: DocumentProgressResponse | None = None,
) -> DocumentResponse:
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
        progress=progress,
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
    require_tenant_metadata(collection, metadata)
    return metadata


def content_hash_match(
    collection: dict,
    content_hash: str,
    metadata: dict,
) -> sa.Select:
    stmt = (
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .where(Document.content_hash == content_hash)
        .limit(1)
    )
    field = tenant_field(collection)
    if field:
        stmt = stmt.where(Document.meta.contains({field: metadata[field]}))
    return stmt


async def read_upload_content(
    file: UploadFile,
    *,
    max_size: int,
    budget: UploadBudget | None = None,
) -> bytes:
    chunks = []
    total_size = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            max_mb = sync_value("max_upload_size_mb")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {max_mb}MB",
            )
        if budget is not None:
            budget.consume(len(chunk))
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
    logger.info("upload stored", key=storage_key, size=len(content))

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
    await collection_cache.invalidate(collection_name)

    try:
        await ingestion_queue.enqueue(
            create_ingestion_job(
                document_id=str(doc_id),
                file_path=storage_key,
                collection_name=collection_name,
                collection=collection,
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
    try:
        target_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    row = (
        await session.execute(
            sa.select(Document, Collection.name)
            .join(Collection, Collection.id == Document.collection_id)
            .where(Document.id == target_id)
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
