from __future__ import annotations

import random
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
from bigrag.services.event_bus import event_bus
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.staged_files import clear_document_staged_file

logger = get_logger("bigrag.queue")

_PERMANENT_ERRORS = queue_embedding.PERMANENT_ERRORS
_delete_document_vectors_after_failure = queue_embedding.delete_document_vectors_after_failure


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
    queue._emit(
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
            queue._emit(
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

        async with session_factory()() as session:
            await session.execute(
                sa.update(Document)
                .where(Document.id == doc_uuid)
                .values(
                    status="ready",
                    chunk_count=total_inserted,
                    token_count=token_count,
                    multimodal_element_count=element_count,
                    error_message=partial_msg,
                )
            )
            await session.commit()

        await clear_document_staged_file(doc_uuid, job.file_path)

        from bigrag.services.retrieval import invalidate_collection_query_cache

        await invalidate_collection_query_cache(job.collection_name)
        if job.multimodal_enrichment_enabled and element_count > 0:
            from bigrag.services.jobs.actors import enqueue_multimodal_enrichment

            enqueue_multimodal_enrichment(job.document_id)
        total_elapsed = time.monotonic() - start_time
        await queue._redis.hincrby(queue_state.STATS_KEY, "completed", 1)
        await queue._redis.hincrby(queue_state.STATS_KEY, "processing", -1)
        logger.debug(
            "job complete",
            prefix=prefix,
            chunks=total_inserted,
            elapsed=round(total_elapsed, 2),
        )
        await queue._fanout_webhook_event(
            queue._emit(
                doc,
                "complete",
                "complete",
                f"Done — {total_inserted} chunks in {total_elapsed:.1f}s",
                1.0,
                collection_name=job.collection_name,
                chunks=total_inserted,
                elapsed=round(total_elapsed, 2),
            )
        )
        event_bus.complete(doc)

    except Exception as e:
        total_elapsed = time.monotonic() - start_time
        await queue._redis.hincrby(queue_state.STATS_KEY, "processing", -1)
        safe_error = sanitize_message_text(str(e)) or "ingestion failed"
        logger.error(f"{job.collection_name} | failed after {total_elapsed:.1f}s | {safe_error}")

        is_permanent = isinstance(e, _PERMANENT_ERRORS)

        if isinstance(e, queue_state.IngestionCancelledError):
            await _delete_document_vectors_after_failure(
                vector_store,
                job.collection_name,
                doc,
                prefix=prefix,
                log_message="failed to clean up cancelled vectors",
            )
            safe_message = sanitize_message_text(str(e)) or "ingestion cancelled"
            await _update_doc(status="failed", error_message=safe_message)
            await clear_document_staged_file(doc_uuid, job.file_path)
            queue._emit(
                doc,
                "cancelled",
                "failed",
                safe_message,
                0.0,
                collection_name=job.collection_name,
            )
            event_bus.complete(doc)
        elif not is_permanent and job.attempt < job.max_attempts:
            from bigrag.services.jobs.actors import enqueue_ingestion_job

            await _delete_document_vectors_after_failure(
                vector_store,
                job.collection_name,
                doc,
                prefix=prefix,
                log_message="failed to clean up partial vectors",
            )

            delay = min(2**job.attempt, 30) + random.uniform(0, min(2**job.attempt, 10))
            queue._emit(
                doc,
                "retrying",
                "processing",
                f"Attempt {job.attempt} failed, retrying in {delay}s",
                0.0,
                collection_name=job.collection_name,
                error=safe_error,
                attempt=job.attempt,
                delay=delay,
            )
            await _update_doc(
                status="pending",
                error_message=f"Attempt {job.attempt} failed: {safe_error}. Retrying...",
            )
            enqueue_ingestion_job(job, delay_seconds=delay)
        else:
            reason = "permanent error" if is_permanent else f"{job.max_attempts} attempts exhausted"
            await _delete_document_vectors_after_failure(
                vector_store,
                job.collection_name,
                doc,
                prefix=prefix,
                log_message="failed to clean up permanently failed vectors",
            )
            await queue._redis.hincrby(queue_state.STATS_KEY, "failed", 1)
            await queue._redis.lpush(queue_state.DEAD_LETTER_KEY, job.serialize())
            await queue._redis.ltrim(queue_state.DEAD_LETTER_KEY, 0, 999)
            safe_message = safe_error
            await _update_doc(status="failed", error_message=safe_message)
            await clear_document_staged_file(doc_uuid, job.file_path)
            logger.debug(
                "job permanently failed",
                prefix=prefix,
                reason=reason,
                error_type=type(e).__name__,
            )
            await queue._fanout_webhook_event(
                queue._emit(
                    doc,
                    "failed",
                    "failed",
                    safe_message,
                    0.0,
                    collection_name=job.collection_name,
                    attempts=job.attempt,
                )
            )
            event_bus.complete(doc)
