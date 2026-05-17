from __future__ import annotations

import asyncio
from pathlib import Path

import sqlalchemy as sa
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.db.session import get_session
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.document import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchGetRequest,
    BatchGetResponse,
    BatchStatusRequest,
    BatchStatusResponse,
    DocumentListResponse,
    DocumentStatusResponse,
)
from bigrag.routers import ensure_embedding_or_400, get_collection_or_404
from bigrag.routers._documents import (
    document_response,
    parse_form_metadata,
)
from bigrag.routers.documents import router
from bigrag.routers.documents_progress import document_progress_map, publish_queued_progress
from bigrag.routers.documents_uploads import (
    metadata_or_400,
    upload_extension_or_400,
    uuid_or_404,
    validated_upload_to_temp,
)
from bigrag.services import audit, collection_cache
from bigrag.services.documents import (
    UploadBudget,
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.storage import get_storage
from bigrag.services.tenant_enforcement import tenant_field
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.documents.batch")


async def _existing_documents_by_hash(
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


async def _cleanup_stored_paths(paths: list[str]) -> None:
    storage = get_storage()
    for path in paths:
        try:
            await storage.delete(path)
        except Exception as exc:
            logger.warning("batch upload cleanup failed", path=path, error=str(exc))


async def _enqueue_batch_documents(
    docs: list[Document],
    collection_name: str,
    collection: dict,
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
            publish_queued_progress(doc, collection_name, "Queued for ingestion")
        except Exception as exc:
            logger.exception(
                "batch upload: enqueue failed, marking document failed",
                doc_id=str(doc.id),
                collection=collection_name,
            )
            doc.status = "failed"
            doc.error_message = f"enqueue failed: {exc.__class__.__name__}: {exc}"
            failed = True
    return failed


async def _persist_batch_upload_documents(
    *,
    session: AsyncSession,
    collection_name: str,
    collection: dict,
    metadata: dict,
    pending: list[tuple[UploadFile, str, Path, str, int]],
) -> list[tuple[Document, bool]]:
    hashes = list(dict.fromkeys(item[3] for item in pending))
    seen_by_hash = await _existing_documents_by_hash(session, collection, metadata, hashes)
    ordered: list[tuple[Document, bool]] = []
    new_docs: list[Document] = []
    stored_paths: list[str] = []
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
            stored_paths.append(storage_key)
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
                await _cleanup_stored_paths(stored_paths)
                refetched = await _existing_documents_by_hash(session, collection, metadata, hashes)
                rebuilt: list[tuple[Document, bool]] = []
                for _file, _ext, _tmp, content_hash, _size in pending:
                    existing = refetched.get(content_hash)
                    if existing is not None:
                        rebuilt.append((existing, True))
                return rebuilt
    except Exception:
        await session.rollback()
        await _cleanup_stored_paths(stored_paths)
        raise

    if new_docs:
        if await _enqueue_batch_documents(new_docs, collection_name, collection):
            await session.commit()
        await collection_cache.invalidate(collection_name)

    return ordered


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
    ensure_embedding_or_400(collection)

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
    shared_meta = metadata_or_400(
        collection,
        metadata,
        prepare_document_metadata,
        parse_form_metadata,
    )

    pending: list[tuple[UploadFile, str, Path, str, int]] = []
    try:
        for file in files:
            file_ext = upload_extension_or_400(file.filename, batch=True)
            tmp_path, content_hash, size = await validated_upload_to_temp(
                file,
                file_ext,
                max_size=max_size,
                budget=budget,
                batch=True,
            )
            pending.append((file, file_ext, tmp_path, content_hash, size))

        ordered_docs = await _persist_batch_upload_documents(
            session=session,
            collection_name=collection_name,
            collection=collection,
            metadata=shared_meta,
            pending=pending,
        )
    finally:
        for _file, _ext, tmp_path, _hash, _size in pending:
            try:
                tmp_path.unlink()
            except OSError:
                pass
    unique_docs = list({str(doc.id): doc for doc, _deduped in ordered_docs}.values())
    progresses = await document_progress_map(unique_docs, collection_name)
    created = [
        document_response(doc, deduped=deduped, progress=progresses[str(doc.id)])
        for doc, deduped in ordered_docs
    ]

    logger.info("batch upload", collection=collection_name, files=len(created))
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

    uuids = [uuid_or_404(d, "Document") for d in body.document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()

    progresses = await document_progress_map(list(docs), collection_name)
    documents = []
    for doc in docs:
        documents.append(
            DocumentStatusResponse(
                id=str(doc.id),
                status=doc.status,
                error_message=doc.error_message,
                chunk_count=doc.chunk_count,
                progress=progresses[str(doc.id)],
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

    uuids = [uuid_or_404(d, "Document") for d in body.document_ids]
    docs = (
        await session.scalars(
            sa.select(Document)
            .where(Document.collection_id == collection["id"])
            .where(Document.id.in_(uuids))
        )
    ).all()

    progresses = await document_progress_map(list(docs), collection_name)
    documents = [document_response(d, progress=progresses[str(d.id)]) for d in docs]
    logger.info(
        "batch get",
        collection=collection_name,
        requested=len(uuids),
        found=len(documents),
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

    uuids = [uuid_or_404(d, "Document") for d in body.document_ids]
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
            await vector_store.delete_by_document(
                collection_name,
                doc_id,
                provider=collection.get("vector_store_provider"),
            )
            await get_storage().delete(doc.file_path)
            return True
        except Exception as exc:
            logger.error("batch delete failed", document_id=doc_id, error=repr(exc))
            errors.append({"document_id": doc_id, "error": str(exc)})
            return False

    await ingestion_queue.cancel_documents(list(by_id))
    results = await asyncio.gather(*[_delete_one(doc_id, doc) for doc_id, doc in by_id.items()])
    deleted = sum(1 for r in results if r)

    deleted_ids = [
        uuid_or_404(d, "Document") for d, ok in zip(by_id.keys(), results, strict=True) if ok
    ]
    if deleted_ids:
        await session.execute(sa.delete(Document).where(Document.id.in_(deleted_ids)))
    await recount_collection_documents(session, collection["id"])
    await session.commit()
    await collection_cache.invalidate(collection_name)
    await invalidate_collection_query_cache(collection_name)

    logger.info("batch delete", collection=collection_name, deleted=deleted, errors=len(errors))
    audit.record(
        request,
        user=user,
        action="document.batch_delete",
        resource_type="collection",
        resource_id=str(collection["id"]),
        metadata={"collection": collection_name, "deleted": deleted, "errors": len(errors)},
    )
    return BatchDeleteResponse(status="ok", deleted=deleted, errors=errors)
