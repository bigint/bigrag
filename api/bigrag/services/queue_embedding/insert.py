from __future__ import annotations

import asyncio
import time

from bigrag.logging import get_logger
from bigrag.services.embedding_rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
)
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_embedding.embed import PERMANENT_ERRORS, embed_with_cache
from bigrag.services.queue_state import IngestionCancelledError

logger = get_logger("bigrag.queue")


async def chunk_and_embed(
    job: IngestionJob,
    text: str,
    prefix: str,
    *,
    vector_store,
    emit,
    ensure_job_current,
) -> tuple[int, int]:
    from bigrag.exceptions import ValidationError
    from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
    from bigrag.services.collection_config import get_embedding_model_for
    from bigrag.services.ingestion import chunk_document
    from bigrag.services.runtime_settings import get_value

    if vector_store is None:
        from bigrag.services.vector_store import vector_store

    t0 = time.monotonic()
    logger.info("loading collection config", prefix=prefix, collection=job.collection_name)
    collection = await get_collection_or_404(job.collection_name)
    try:
        embedding_model = get_embedding_model_for(collection)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    elapsed = time.monotonic() - t0
    logger.info(
        "model loaded",
        prefix=prefix,
        provider=job.embedding_provider,
        model=job.embedding_model,
        elapsed=round(elapsed, 2),
    )
    cooldown_key = rate_limit_cooldown_key(
        embedding_model,
        job.embedding_provider,
        job.embedding_model,
        job.embedding_dimension,
    )
    emit(
        job.document_id,
        "model_loaded",
        "processing",
        f"Loaded {job.embedding_model}",
        0.10,
        collection_name=job.collection_name,
        provider=job.embedding_provider,
        model=job.embedding_model,
        elapsed=round(elapsed, 2),
    )

    strategy = getattr(job, "chunk_strategy", "paragraph") or "paragraph"
    chunks = await asyncio.to_thread(
        chunk_document,
        text,
        job.chunk_size,
        job.chunk_overlap,
        strategy,
    )
    if not chunks:
        raise ValueError("Document produced no chunks")
    logger.info("document chunked", prefix=prefix, chunks=len(chunks), strategy=strategy)
    emit(
        job.document_id,
        "chunked",
        "processing",
        f"Split into {len(chunks)} chunks",
        0.45,
        collection_name=job.collection_name,
        chunks=len(chunks),
        chunk_size=job.chunk_size,
    )

    await ensure_job_current(job)
    logger.info(
        "ensuring vector collection",
        prefix=prefix,
        collection=job.collection_name,
        dimension=job.embedding_dimension,
    )
    await vector_store.create_collection(
        job.collection_name,
        job.embedding_dimension,
        tenant_field=getattr(job, "tenant_field", None),
        provider=job.vector_store_provider,
    )
    await ensure_job_current(job)

    batch_size = await get_value("ingestion_batch_size")
    total_inserted = 0
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    doc = job.document_id

    max_batch_retries = 3
    batch_backoff_base = 2

    batches: list[tuple[int, int, int, list]] = []
    for batch_start in range(0, len(chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunks))
        batch_num = batch_start // batch_size + 1
        batches.append((batch_num, batch_start, batch_end, chunks[batch_start:batch_end]))

    async def _embed_one(
        batch_num: int,
        batch_start: int,
        batch_end: int,
        batch_chunks: list,
    ) -> tuple[int, int, int, list, list[list[float]], float]:
        batch_texts = [c.text for c in batch_chunks]
        rate_limit_attempt = 0
        attempt = 0
        while True:
            attempt += 1
            try:
                t0 = time.monotonic()
                logger.info(
                    "batch embedding start",
                    prefix=prefix,
                    batch=batch_num,
                    total_batches=total_batches,
                    chunks=len(batch_texts),
                    attempt=attempt,
                )
                embeddings = await embed_with_cache(
                    batch_texts,
                    embedding_model,
                    job.embedding_provider,
                    job.embedding_model,
                    job.embedding_dimension,
                )
                embed_elapsed = time.monotonic() - t0
                return batch_num, batch_start, batch_end, batch_chunks, embeddings, embed_elapsed
            except PERMANENT_ERRORS:
                raise
            except Exception as exc:
                if is_rate_limit_error(exc):
                    rate_limit_attempt += 1
                    if rate_limit_attempt >= MAX_RATE_LIMIT_RETRIES:
                        logger.error(
                            "batch exhausted rate limit retries",
                            prefix=prefix,
                            batch=batch_num,
                            total_batches=total_batches,
                            chunks=len(batch_texts),
                            attempt=attempt,
                            max_rate_limit_attempts=MAX_RATE_LIMIT_RETRIES,
                            error=repr(exc),
                        )
                        raise
                    fallback_delay = batch_backoff_base ** min(rate_limit_attempt, 5)
                    delay = rate_limit_delay(exc, float(fallback_delay))
                    await record_rate_limit_cooldown(cooldown_key, delay)
                    logger.warning(
                        "batch rate limited",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        attempt=attempt,
                        rate_limit_attempt=rate_limit_attempt,
                        max_rate_limit_attempts=MAX_RATE_LIMIT_RETRIES,
                        error=repr(exc),
                        retrying_in=round(delay, 3),
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

    embed_sem = asyncio.Semaphore(8)

    async def _embed_one_bounded(bn, bs, be, bc):
        async with embed_sem:
            return await _embed_one(bn, bs, be, bc)

    embed_results = await asyncio.gather(
        *[_embed_one_bounded(bn, bs, be, bc) for bn, bs, be, bc in batches]
    )
    embed_results.sort(key=lambda r: r[0])

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
                metadata = [
                    {"char_start": c.char_start, "char_end": c.char_end} for c in batch_chunks
                ]
                logger.info(
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
                    provider=job.vector_store_provider,
                )
                try:
                    await ensure_job_current(job)
                except IngestionCancelledError:
                    await vector_store.delete_by_document(
                        job.collection_name,
                        doc,
                        provider=job.vector_store_provider,
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
                        provider=job.vector_store_provider,
                    )
                except Exception as cleanup_exc:
                    logger.warning(
                        "batch cleanup before retry failed",
                        prefix=prefix,
                        batch=batch_num,
                        error=repr(cleanup_exc),
                    )
                transient_attempt += 1
                if transient_attempt >= max_batch_retries:
                    logger.error(
                        "batch exhausted retries",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        chunks=len(batch_texts),
                        error=repr(exc),
                    )
                    raise
                delay = batch_backoff_base**transient_attempt
                logger.warning(
                    "batch attempt failed",
                    prefix=prefix,
                    batch=batch_num,
                    total_batches=total_batches,
                    attempt=transient_attempt,
                    max_attempts=max_batch_retries,
                    error=repr(exc),
                    retrying_in=delay,
                )
                await asyncio.sleep(delay)
        total_inserted += count

        progress = 0.45 + (0.45 * batch_num / total_batches)
        logger.info(
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

    return total_inserted, len(chunks)
