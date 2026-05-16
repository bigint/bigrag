from __future__ import annotations

import asyncio
import time

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.embedding import truncate_to_tokens
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_state import IngestionCancelledError

logger = get_logger("bigrag.queue")

EMBEDDING_TIMEOUT_SECONDS = 60
PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)


async def embed_with_cache(
    texts: list[str],
    model,
    provider: str,
    model_name: str,
    dimension: int,
) -> list[list[float]]:
    cache_texts, _ = truncate_to_tokens(texts, model_name)
    logger.info(
        "embedding cache lookup",
        provider=provider,
        model=model_name,
        dimension=dimension,
        inputs=len(texts),
    )
    cached = await embedding_cache.get_many(cache_texts, provider, model_name, dimension)
    missing_idx = [i for i in range(len(texts)) if i not in cached]
    logger.info(
        "embedding cache result",
        provider=provider,
        model=model_name,
        hits=len(texts) - len(missing_idx),
        misses=len(missing_idx),
    )
    if missing_idx:
        missing_by_cache_text: dict[str, int] = {}
        for idx in missing_idx:
            missing_by_cache_text.setdefault(cache_texts[idx], idx)
        provider_idx = list(missing_by_cache_text.values())
        missing_texts = [texts[i] for i in provider_idx]
        missing_cache_texts = [cache_texts[i] for i in provider_idx]
        t0 = time.monotonic()
        logger.info(
            "embedding provider request",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
        )
        fresh = await asyncio.wait_for(
            model.embed(missing_texts),
            timeout=EMBEDDING_TIMEOUT_SECONDS,
        )
        logger.info(
            "embedding provider response",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
            elapsed=round(time.monotonic() - t0, 2),
        )
        if len(fresh) != len(missing_texts):
            raise ValueError(
                f"embedding provider returned {len(fresh)} vectors for {len(missing_texts)} inputs"
            )
        await embedding_cache.put_many(missing_cache_texts, fresh, provider, model_name, dimension)
        fresh_by_cache_text = dict(zip(missing_cache_texts, fresh, strict=False))
        for idx in missing_idx:
            cached[idx] = fresh_by_cache_text[cache_texts[idx]]
    return [cached[i] for i in range(len(texts))]


async def delete_document_vectors_after_failure(
    store,
    collection_name: str,
    document_id: str,
    *,
    prefix: str,
    log_message: str,
) -> None:
    try:
        await store.delete_by_document(collection_name, document_id)
    except Exception as cleanup_err:
        logger.warning(log_message, prefix=prefix, error=repr(cleanup_err))


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

    for batch_start in range(0, len(chunks), batch_size):
        batch_end = min(batch_start + batch_size, len(chunks))
        batch_chunks = chunks[batch_start:batch_end]
        batch_texts = [c.text for c in batch_chunks]
        batch_num = batch_start // batch_size + 1

        embed_elapsed = 0.0
        insert_elapsed = 0.0
        count = 0
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
                if attempt >= max_batch_retries:
                    logger.error(
                        "batch exhausted retries",
                        prefix=prefix,
                        batch=batch_num,
                        total_batches=total_batches,
                        chunks=len(batch_texts),
                        error=repr(exc),
                    )
                    raise
                delay = batch_backoff_base**attempt
                logger.warning(
                    "batch attempt failed",
                    prefix=prefix,
                    batch=batch_num,
                    total_batches=total_batches,
                    attempt=attempt,
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
