from __future__ import annotations

import hashlib
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import Collection, Document
from bigrag.exceptions import ValidationError
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.services import collection_cache, metadata_schema
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import sync_value
from bigrag.services.staged_files import clear_document_staged_file
from bigrag.services.storage import get_storage
from bigrag.services.tenant_enforcement import require_tenant_metadata, tenant_field

_COLLECTION_SLUG_RE = re.compile(r"[a-zA-Z0-9_-]{1,128}")

logger = get_logger("bigrag.services.documents")

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


async def stream_upload_to_temp(
    upload: UploadFile,
    *,
    max_size: int,
    budget: UploadBudget | None = None,
) -> tuple[Path, str, int]:
    temp_dir = settings.upload_dir or None
    if temp_dir:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir)
    tmp_path = Path(tmp.name)
    hasher = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = await upload.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                max_mb = sync_value("max_upload_size_mb")
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max size: {max_mb}MB",
                )
            if budget is not None:
                budget.consume(len(chunk))
            hasher.update(chunk)
            tmp.write(chunk)
    except BaseException:
        try:
            tmp.close()
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    tmp.flush()
    tmp.close()
    return tmp_path, hasher.hexdigest(), total


async def persist_document(
    *,
    session: AsyncSession,
    collection_name: str,
    collection: dict,
    filename: str,
    source: Path,
    file_size: int,
    metadata: dict,
    content_hash: str,
    raise_on_enqueue_failure: bool,
) -> Document:
    if not _COLLECTION_SLUG_RE.fullmatch(collection_name):
        raise ValidationError(f"Invalid collection name: {collection_name!r}")
    doc_id = uuid7()
    file_ext = Path(filename or "document").suffix
    storage_key = f"{collection_name}/{doc_id}{file_ext}"
    storage = get_storage()

    with source.open("rb") as fh:
        await storage.put_stream(storage_key, fh, size=file_size)
    logger.info("upload staged", key=storage_key, size=file_size)

    doc = Document(
        id=doc_id,
        collection_id=collection["id"],
        filename=filename or "document",
        file_type=file_ext.lstrip("."),
        file_size=file_size,
        file_path=storage_key,
        content_hash=content_hash,
        meta=dict(metadata),
    )
    session.add(doc)
    try:
        await session.flush()
        await recount_collection_documents(session, collection["id"])
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await storage.delete(storage_key)
        raise
    except Exception:
        await session.rollback()
        await storage.delete(storage_key)
        raise
    await session.refresh(doc)
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
        doc.error_message = sanitize_message_text(f"enqueue failed: {type(exc).__name__}")
        await session.commit()
        await session.refresh(doc)
        await clear_document_staged_file(doc.id, storage_key)
        if raise_on_enqueue_failure:
            raise HTTPException(
                status_code=503,
                detail=("Ingestion queue unavailable — document saved as failed, retry later."),
            ) from exc

    return doc


async def get_document_with_collection(
    session: AsyncSession,
    document_id: str,
    *,
    pinned_collection: str | None = None,
) -> tuple[Document, str]:
    try:
        target_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    stmt = (
        sa.select(Document, Collection.name)
        .join(Collection, Collection.id == Document.collection_id)
        .where(Document.id == target_id)
    )
    if pinned_collection:
        stmt = stmt.where(Collection.name == pinned_collection)
    row = (await session.execute(stmt)).first()
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
