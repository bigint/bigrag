from __future__ import annotations

import asyncio
import time

from bigrag.logging import get_logger
from bigrag.services.embedding_rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    is_rate_limit_error,
    rate_limit_delay,
)
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_embedding.embed import PERMANENT_ERRORS, embed_with_cache

logger = get_logger("bigrag.queue")

BATCH_BACKOFF_BASE = 2
EMBED_CONCURRENCY = 8


async def embed_all_batches(
    job: IngestionJob,
    prefix: str,
    *,
    embedding_model,
    batches: list[tuple[int, int, int, list]],
    total_batches: int,
) -> list[tuple[int, int, int, list, list[list[float]], float]]:
    async def _embed_batch(
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
                logger.debug(
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
                    fallback_delay = BATCH_BACKOFF_BASE ** min(rate_limit_attempt, 5)
                    delay = rate_limit_delay(exc, float(fallback_delay))
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

    embed_sem = asyncio.Semaphore(EMBED_CONCURRENCY)

    async def _embed_batch_bounded(bn, bs, be, bc):
        async with embed_sem:
            return await _embed_batch(bn, bs, be, bc)

    embed_results = await asyncio.gather(
        *[_embed_batch_bounded(bn, bs, be, bc) for bn, bs, be, bc in batches]
    )
    embed_results.sort(key=lambda r: r[0])
    return embed_results
