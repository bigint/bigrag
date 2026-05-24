from __future__ import annotations

import random
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from bigrag.logging import get_logger
from bigrag.services import queue_embedding, queue_state
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.event_bus import event_bus
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.staged_files import clear_document_staged_file

logger = get_logger("bigrag.queue")

_delete_document_vectors_after_failure = queue_embedding.delete_document_vectors_after_failure


async def finalize_success(
    queue: Any,
    job: IngestionJob,
    *,
    doc: str,
    doc_uuid: uuid.UUID,
    prefix: str,
    start_time: float,
    total_inserted: int,
    pending_enrichment_count: int,
) -> None:
    await clear_document_staged_file(doc_uuid, job.file_path)

    from bigrag.services.retrieval import invalidate_collection_query_cache

    await invalidate_collection_query_cache(job.collection_name)
    if job.should_enrich_multimodal and pending_enrichment_count > 0:
        from bigrag.services.jobs.actors import enqueue_multimodal_enrichment

        enqueue_multimodal_enrichment(job.document_id)
    total_elapsed = time.monotonic() - start_time
    await queue._redis.hincrby(queue_state.STATS_KEY, "completed", 1)
    await queue._redis.hincrby(queue_state.STATS_KEY, "processing", -1)
    await queue._release_job()
    logger.debug(
        "job complete",
        prefix=prefix,
        chunks=total_inserted,
        elapsed=round(total_elapsed, 2),
    )
    await queue._fanout_webhook_event(
        queue._publish_progress(
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


async def finalize_cancelled(
    queue: Any,
    job: IngestionJob,
    error: Exception,
    *,
    vector_store: Any,
    doc: str,
    doc_uuid: uuid.UUID,
    prefix: str,
    update_doc: Callable[..., Awaitable[None]],
) -> None:
    await _delete_document_vectors_after_failure(
        vector_store,
        job.collection_name,
        doc,
        prefix=prefix,
        log_message="failed to clean up cancelled vectors",
    )
    safe_message = sanitize_message_text(str(error)) or "ingestion cancelled"
    await update_doc(status="failed", error_message=safe_message)
    await clear_document_staged_file(doc_uuid, job.file_path)
    await queue._release_job()
    queue._publish_progress(
        doc,
        "cancelled",
        "failed",
        safe_message,
        0.0,
        collection_name=job.collection_name,
    )
    event_bus.complete(doc)


async def finalize_retry(
    queue: Any,
    job: IngestionJob,
    *,
    vector_store: Any,
    doc: str,
    doc_uuid: uuid.UUID,
    prefix: str,
    safe_error: str,
    update_doc: Callable[..., Awaitable[None]],
) -> None:
    await _delete_document_vectors_after_failure(
        vector_store,
        job.collection_name,
        doc,
        prefix=prefix,
        log_message="failed to clean up partial vectors",
    )

    delay = min(2**job.attempt, 30) + random.uniform(0, min(2**job.attempt, 10))
    await queue._release_job()
    try:
        await queue.enqueue_retry(job, delay_seconds=delay)
    except queue_state.QueueFullError:
        await queue._redis.hincrby(queue_state.STATS_KEY, "failed", 1)
        await update_doc(
            status="failed",
            error_message=f"Attempt {job.attempt} failed: {safe_error}. Queue full, not retried.",
        )
        await clear_document_staged_file(doc_uuid, job.file_path)
        queue._publish_progress(
            doc,
            "failed",
            "failed",
            safe_error,
            0.0,
            collection_name=job.collection_name,
            attempts=job.attempt,
        )
        event_bus.complete(doc)
        return
    queue._publish_progress(
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
    await update_doc(
        status="pending",
        error_message=f"Attempt {job.attempt} failed: {safe_error}. Retrying...",
    )


async def finalize_permanent(
    queue: Any,
    job: IngestionJob,
    error: Exception,
    *,
    vector_store: Any,
    doc: str,
    doc_uuid: uuid.UUID,
    prefix: str,
    safe_error: str,
    is_permanent: bool,
    update_doc: Callable[..., Awaitable[None]],
) -> None:
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
    await update_doc(status="failed", error_message=safe_message)
    await clear_document_staged_file(doc_uuid, job.file_path)
    await queue._release_job()
    logger.debug(
        "job permanently failed",
        prefix=prefix,
        reason=reason,
        error_type=type(error).__name__,
    )
    await queue._fanout_webhook_event(
        queue._publish_progress(
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
