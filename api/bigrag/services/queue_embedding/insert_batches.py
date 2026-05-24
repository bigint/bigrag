from __future__ import annotations

import asyncio
import time

from bigrag.logging import get_logger
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_embedding.chunk_metadata import build_batch_metadata
from bigrag.services.queue_embedding.embed import PERMANENT_ERRORS
from bigrag.services.queue_state import IngestionCancelledError

logger = get_logger("bigrag.queue")

MAX_BATCH_RETRIES = 3
BATCH_BACKOFF_BASE = 2


async def insert_all_batches(
    job: IngestionJob,
    prefix: str,
    *,
    vector_store,
    emit,
    ensure_job_current,
    embed_results: list[tuple[int, int, int, list, list[list[float]], float]],
    elements: list,
    include_elements: bool,
    total_batches: int,
) -> int:
    total_inserted = 0
    doc = job.document_id

    for batch_num, batch_start, batch_end, batch_chunks, embeddings, embed_elapsed in embed_results:
        batch_texts = [c.text for c in batch_chunks]
        insert_elapsed = 0.0
        count = 0
        transient_attempt = 0
        while True:
            try:
                t1 = time.monotonic()
                await ensure_job_current(job)
                ids = [f"{doc}_{i}" for i in range(batch_start, batch_end)]
                doc_ids = [doc] * len(batch_texts)
                indices = list(range(batch_start, batch_end))
                metadata = build_batch_metadata(
                    batch_chunks,
                    document_id=doc,
                    batch_start=batch_start,
                    elements=elements,
                    include_elements=include_elements,
                )
                logger.debug(
                    "batch vector insert start",
                    prefix=prefix,
                    batch=batch_num,
                    total_batches=total_batches,
                    chunks=len(batch_texts),
                )
                count = await vector_store.insert(
                    collection=job.collection_name,
                    ids=ids,
                    document_ids=doc_ids,
                    chunk_indices=indices,
                    texts=batch_texts,
                    embeddings=embeddings,
                    metadata=metadata,
                )
                try:
                    await ensure_job_current(job)
                except IngestionCancelledError:
                    await vector_store.delete_by_document(
                        job.collection_name,
                        doc,
                    )
                    raise
                insert_elapsed = time.monotonic() - t1
                break
            except PERMANENT_ERRORS:
                raise
            except Exception as exc:
                try:
                    await vector_store.delete_by_ids(
                        job.collection_name,
                        [f"{doc}_{i}" for i in range(batch_start, batch_end)],
                    )
                except Exception as cleanup_exc:
                    logger.warning(
                        "batch cleanup before retry failed",
                        prefix=prefix,
                        batch=batch_num,
                        error=repr(cleanup_exc),
                    )
                transient_attempt += 1
                if transient_attempt >= MAX_BATCH_RETRIES:
                    logger.error(
                        "batch exhausted retries",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        chunks=len(batch_texts),
                        error=repr(exc),
                    )
                    raise
                delay = BATCH_BACKOFF_BASE**transient_attempt
                logger.warning(
                    "batch attempt failed",
                    prefix=prefix,
                    batch=batch_num,
                    total_batches=total_batches,
                    attempt=transient_attempt,
                    max_attempts=MAX_BATCH_RETRIES,
                    error=repr(exc),
                    retrying_in=delay,
                )
                await asyncio.sleep(delay)
        total_inserted += count

        progress = 0.45 + (0.45 * batch_num / total_batches)
        logger.debug(
            "batch inserted",
            prefix=prefix,
            batch=batch_num,
            total_batches=total_batches,
            inserted=count,
            embed_elapsed=round(embed_elapsed, 2),
            insert_elapsed=round(insert_elapsed, 2),
        )
        emit(
            doc,
            "embedding",
            "processing",
            f"Batch {batch_num}/{total_batches} — {total_inserted} vectors",
            progress,
            collection_name=job.collection_name,
            batch=batch_num,
            total_batches=total_batches,
            inserted=total_inserted,
            embed_time=round(embed_elapsed, 2),
        )

    return total_inserted
