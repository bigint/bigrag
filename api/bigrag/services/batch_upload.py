from __future__ import annotations

import asyncio
from pathlib import Path

import sqlalchemy as sa
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.services import collection_cache
from bigrag.services.documents import recount_collection_documents
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.staged_files import delete_staged_file_path
from bigrag.services.storage import get_storage
from bigrag.services.tenant_enforcement import tenant_field

logger = get_logger("bigrag.services.batch_upload")


async def existing_documents_by_hash(
    session: AsyncSession,
    collection: dict,
    metadata: dict,
    content_hashes: list[str],
) -> dict[str, Document]:
    if not content_hashes:
        return {}
    stmt = (
        sa.select(Document)
        .where(Document.collection_id == collection["id"])
        .where(Document.content_hash.in_(content_hashes))
        .order_by(Document.created_at.asc(), Document.id.asc())
    )
    field = tenant_field(collection)
    if field:
        stmt = stmt.where(Document.meta.contains({field: metadata[field]}))
    docs = (await session.scalars(stmt)).all()
    out: dict[str, Document] = {}
    for doc in docs:
        if doc.content_hash:
            out.setdefault(doc.content_hash, doc)
    return out


async def cleanup_staged_paths(paths: list[str]) -> None:
    for path in paths:
        await delete_staged_file_path(path)


async def enqueue_batch_documents(
    docs: list[Document],
    collection_name: str,
    collection: dict,
    progress_publisher,
) -> bool:
    failed = False
    for doc in docs:
        try:
            await ingestion_queue.enqueue(
                create_ingestion_job(
                    document_id=str(doc.id),
                    file_path=doc.file_path,
                    collection_name=collection_name,
                    collection=collection,
                )
            )
            progress_publisher(doc, collection_name, "Queued for ingestion")
        except Exception as exc:
            logger.exception(
                "batch upload: enqueue failed, marking document failed",
                doc_id=str(doc.id),
                collection=collection_name,
            )
            doc.status = "failed"
            safe_error = sanitize_message_text(str(exc)) or exc.__class__.__name__
            doc.error_message = f"enqueue failed: {safe_error}"
            if await delete_staged_file_path(doc.file_path):
                doc.file_path = ""
            failed = True
    return failed


async def persist_batch_upload_documents(
    *,
    session: AsyncSession,
    collection_name: str,
    collection: dict,
    metadata: dict,
    pending: list[tuple[UploadFile, str, Path, str, int]],
    progress_publisher,
) -> list[tuple[Document, bool]]:
    hashes = list(dict.fromkeys(item[3] for item in pending))
    seen_by_hash = await existing_documents_by_hash(session, collection, metadata, hashes)
    ordered: list[tuple[Document, bool]] = []
    new_docs: list[Document] = []
    staged_paths: list[str] = []
    storage = get_storage()
    upload_semaphore = asyncio.Semaphore(4)

    async def _put_one(storage_key: str, tmp_path: Path, size: int) -> None:
        async with upload_semaphore:
            with tmp_path.open("rb") as fh:
                await storage.put_stream(storage_key, fh, size=size)

    try:
        put_tasks: list[asyncio.Task] = []
        for file, file_ext, tmp_path, content_hash, size in pending:
            existing = seen_by_hash.get(content_hash)
            if existing is not None:
                ordered.append((existing, True))
                continue

            doc_id = uuid7()
            filename = file.filename or "document"
            storage_key = f"{collection_name}/{doc_id}{file_ext}"
            put_tasks.append(asyncio.create_task(_put_one(storage_key, tmp_path, size)))
            staged_paths.append(storage_key)
            doc = Document(
                id=doc_id,
                collection_id=collection["id"],
                filename=filename,
                file_type=file_ext.lstrip("."),
                file_size=size,
                file_path=storage_key,
                content_hash=content_hash,
                meta=dict(metadata),
            )
            session.add(doc)
            seen_by_hash[content_hash] = doc
            new_docs.append(doc)
            ordered.append((doc, False))

        if put_tasks:
            await asyncio.gather(*put_tasks)

        if new_docs:
            try:
                await session.flush()
                await recount_collection_documents(session, collection["id"])
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await cleanup_staged_paths(staged_paths)
                refetched = await existing_documents_by_hash(session, collection, metadata, hashes)
                rebuilt: list[tuple[Document, bool]] = []
                for _file, _ext, _tmp, content_hash, _size in pending:
                    existing = refetched.get(content_hash)
                    if existing is not None:
                        rebuilt.append((existing, True))
                return rebuilt
    except Exception:
        await session.rollback()
        await cleanup_staged_paths(staged_paths)
        raise

    if new_docs:
        if await enqueue_batch_documents(new_docs, collection_name, collection, progress_publisher):
            await session.commit()
        await collection_cache.invalidate(collection_name)

    return ordered
