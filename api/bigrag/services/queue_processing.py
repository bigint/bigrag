from __future__ import annotations

import time
import uuid
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Document
from bigrag.logging import get_logger
from bigrag.services import queue_embedding, queue_state
from bigrag.services.document_elements import replace_document_elements
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_finalize import (
    finalize_cancelled,
    finalize_permanent,
    finalize_retry,
    finalize_success,
)

logger = get_logger("bigrag.queue")

_PERMANENT_ERRORS = queue_embedding.PERMANENT_ERRORS


async def process_job(queue: Any, worker_id: int | str, job: IngestionJob) -> None:
    vector_store = queue._vector_store
    if vector_store is None:
        from bigrag.services.vector_store import vector_store

    doc_uuid = uuid.UUID(job.document_id)

    async def _update_doc(**values) -> None:
        async with session_factory()() as session:
            await session.execute(
                sa.update(Document).where(Document.id == doc_uuid).values(**values)
            )
            await session.commit()

    job.attempt += 1
    prefix = f"[worker-{worker_id}] [job={job.job_id}] [doc={job.document_id}]"
    doc = job.document_id

    await queue._redis.hincrby(queue_state.STATS_KEY, "processing", 1)
    logger.debug(
        "job starting",
        prefix=prefix,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
    )
    queue._publish_progress(
        doc,
        "queued",
        "processing",
        "Starting ingestion",
        0.0,
        collection_name=job.collection_name,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
    )

    start_time = time.monotonic()

    try:
        await queue._ensure_job_current(job)
        await _update_doc(status="processing")
        await queue._fanout_webhook_event(
            queue._publish_progress(
                doc,
                "processing",
                "processing",
                "Preparing document",
                0.05,
                collection_name=job.collection_name,
            )
        )

        parsed = await queue._convert_document(job, prefix)
        await queue._ensure_job_current(job)
        async with session_factory()() as session:
            element_count = await replace_document_elements(
                session,
                document_id=doc_uuid,
                elements=parsed.elements,
                enrichment_enabled=job.multimodal_enrichment_enabled,
            )
            await session.commit()

        total_inserted, total_expected = await queue._chunk_and_embed(job, parsed, prefix)
        token_count = len(parsed.text) // 4

        if total_inserted == 0:
            raise RuntimeError(f"All {total_expected} chunk batches failed embedding/insert")

        partial_msg = (
            f"Partial: {total_inserted}/{total_expected} chunks embedded"
            if total_inserted < total_expected
            else None
        )

        await queue._ensure_job_current(job)
        async with session_factory()() as session:
            await session.execute(
                sa.update(Document)
                .where(Document.id == doc_uuid)
                .where(Document.status == "processing")
                .values(
                    status="ready",
                    chunk_count=total_inserted,
                    token_count=token_count,
                    multimodal_element_count=element_count,
                    error_message=partial_msg,
                )
            )
            await session.commit()

        await finalize_success(
            queue,
            job,
            doc=doc,
            doc_uuid=doc_uuid,
            prefix=prefix,
            start_time=start_time,
            total_inserted=total_inserted,
            element_count=element_count,
        )

    except Exception as e:
        total_elapsed = time.monotonic() - start_time
        await queue._redis.hincrby(queue_state.STATS_KEY, "processing", -1)
        safe_error = sanitize_message_text(str(e)) or "ingestion failed"
        logger.error(f"{job.collection_name} | failed after {total_elapsed:.1f}s | {safe_error}")

        is_permanent = isinstance(e, _PERMANENT_ERRORS)

        if isinstance(e, queue_state.IngestionCancelledError):
            await finalize_cancelled(
                queue,
                job,
                e,
                vector_store=vector_store,
                doc=doc,
                doc_uuid=doc_uuid,
                prefix=prefix,
                update_doc=_update_doc,
            )
        elif not is_permanent and job.attempt < job.max_attempts:
            await finalize_retry(
                queue,
                job,
                vector_store=vector_store,
                doc=doc,
                doc_uuid=doc_uuid,
                prefix=prefix,
                safe_error=safe_error,
                update_doc=_update_doc,
            )
        else:
            await finalize_permanent(
                queue,
                job,
                e,
                vector_store=vector_store,
                doc=doc,
                doc_uuid=doc_uuid,
                prefix=prefix,
                safe_error=safe_error,
                is_permanent=is_permanent,
                update_doc=_update_doc,
            )
