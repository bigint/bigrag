from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document
from bigrag.logging import get_logger
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.queue import ingestion_queue
from bigrag.services.staged_files import delete_staged_file_path
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.services.document_deletion")

DOCUMENT_DELETE_CHUNK_SIZE = 1000
_FILE_DELETE_CONCURRENCY = 16
_VECTOR_DELETE_CONCURRENCY = 16


@dataclass(frozen=True)
class DocumentDeleteCandidate:
    id: uuid.UUID
    filename: str
    file_path: str


@dataclass(frozen=True)
class BatchDeleteChunkResult:
    deleted: int
    errors: list[dict[str, str]]


async def delete_document_batch_chunk(
    *,
    session: AsyncSession,
    collection_name: str,
    collection_id: uuid.UUID,
    document_ids: Sequence[str],
    document_uuids: Sequence[uuid.UUID],
) -> BatchDeleteChunkResult:
    candidates = await _delete_candidates(session, collection_id, document_uuids)
    by_id = {str(candidate.id): candidate for candidate in candidates}
    errors = [
        {"document_id": document_id, "error": "Document not found"}
        for document_id, document_uuid in zip(document_ids, document_uuids, strict=True)
        if str(document_uuid) not in by_id
    ]
    if not candidates:
        return BatchDeleteChunkResult(deleted=0, errors=errors)

    await ingestion_queue.cancel_documents([str(candidate.id) for candidate in candidates])
    staged_candidates, staged_errors = await _delete_staged_files(candidates)
    errors.extend(staged_errors)
    vector_candidates, vector_errors = await _delete_vectors(collection_name, staged_candidates)
    errors.extend(vector_errors)

    if not vector_candidates:
        return BatchDeleteChunkResult(deleted=0, errors=errors)

    deleted_ids = [candidate.id for candidate in vector_candidates]
    await session.execute(sa.delete(Document).where(Document.id.in_(deleted_ids)))
    await session.execute(
        sa.update(Collection)
        .where(Collection.id == collection_id)
        .values(document_count=sa.func.greatest(Collection.document_count - len(deleted_ids), 0))
    )
    await session.commit()
    return BatchDeleteChunkResult(deleted=len(deleted_ids), errors=errors)


async def _delete_candidates(
    session: AsyncSession,
    collection_id: uuid.UUID,
    document_uuids: Sequence[uuid.UUID],
) -> list[DocumentDeleteCandidate]:
    rows = (
        await session.execute(
            sa.select(Document.id, Document.filename, Document.file_path)
            .where(Document.collection_id == collection_id)
            .where(Document.id.in_(document_uuids))
        )
    ).all()
    return [
        DocumentDeleteCandidate(id=document_id, filename=filename, file_path=file_path)
        for document_id, filename, file_path in rows
    ]


async def _delete_staged_files(
    candidates: Sequence[DocumentDeleteCandidate],
) -> tuple[list[DocumentDeleteCandidate], list[dict[str, str]]]:
    semaphore = asyncio.Semaphore(_FILE_DELETE_CONCURRENCY)

    async def delete_one(
        candidate: DocumentDeleteCandidate,
    ) -> tuple[DocumentDeleteCandidate | None, dict[str, str] | None]:
        async with semaphore:
            try:
                await delete_staged_file_path(candidate.file_path, raise_on_failure=True)
            except Exception as exc:
                logger.error(
                    "batch delete staged cleanup failed",
                    document_id=str(candidate.id),
                    error=repr(exc),
                )
                return None, {
                    "document_id": str(candidate.id),
                    "error": safe_error_detail(
                        exc,
                        "Staged file cleanup failed. Try deleting the document again.",
                    ),
                }
        return candidate, None

    results = await asyncio.gather(*(delete_one(candidate) for candidate in candidates))
    deleted = [candidate for candidate, _error in results if candidate is not None]
    errors = [error for _candidate, error in results if error is not None]
    return deleted, errors


async def _delete_vectors(
    collection_name: str,
    candidates: Sequence[DocumentDeleteCandidate],
) -> tuple[list[DocumentDeleteCandidate], list[dict[str, str]]]:
    if not candidates:
        return [], []
    document_ids = [str(candidate.id) for candidate in candidates]
    try:
        await vector_store.delete_by_documents(collection_name, document_ids)
        return list(candidates), []
    except Exception as exc:
        logger.warning(
            "batch delete vector cleanup failed",
            collection=collection_name,
            documents=len(candidates),
            error=repr(exc),
        )
        return await _delete_vectors_individually(collection_name, candidates)


async def _delete_vectors_individually(
    collection_name: str,
    candidates: Sequence[DocumentDeleteCandidate],
) -> tuple[list[DocumentDeleteCandidate], list[dict[str, str]]]:
    semaphore = asyncio.Semaphore(_VECTOR_DELETE_CONCURRENCY)

    async def delete_one(
        candidate: DocumentDeleteCandidate,
    ) -> tuple[DocumentDeleteCandidate | None, dict[str, str] | None]:
        async with semaphore:
            try:
                await vector_store.delete_by_document(collection_name, str(candidate.id))
            except Exception as exc:
                logger.error(
                    "batch delete vector cleanup failed",
                    document_id=str(candidate.id),
                    error=repr(exc),
                )
                return None, {
                    "document_id": str(candidate.id),
                    "error": safe_error_detail(
                        exc,
                        "Vector cleanup failed. Try deleting the document again.",
                    ),
                }
        return candidate, None

    results = await asyncio.gather(*(delete_one(candidate) for candidate in candidates))
    deleted = [candidate for candidate, _error in results if candidate is not None]
    errors = [error for _candidate, error in results if error is not None]
    return deleted, errors
