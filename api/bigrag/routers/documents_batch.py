from __future__ import annotations

import asyncio
from pathlib import Path

import sqlalchemy as sa
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document
from bigrag.db.session import get_session
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
from bigrag.routers import enforce_collection_pin, ensure_embedding_or_400, get_collection_or_404
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
from bigrag.services.batch_upload import persist_batch_upload_documents
from bigrag.services.document_elements import element_asset_prefix_for_file_path
from bigrag.services.documents import (
    UploadBudget,
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.documents.batch")


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

        ordered_docs = await persist_batch_upload_documents(
            session=session,
            collection_name=collection_name,
            collection=collection,
            metadata=shared_meta,
            pending=pending,
            progress_publisher=publish_queued_progress,
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
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
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
                multimodal_element_count=doc.multimodal_element_count,
                progress=progresses[str(doc.id)],
            )
        )

    return BatchStatusResponse(documents=documents, total=len(documents))


@router.post("/batch/get", response_model=BatchGetResponse)
async def batch_get_documents(
    collection_name: str,
    body: BatchGetRequest,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, collection_name)
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
    enforce_collection_pin(user, collection_name)
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
            storage = get_storage()
            await storage.delete(doc.file_path)
            await storage.delete_prefix(element_asset_prefix_for_file_path(doc.file_path))
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
