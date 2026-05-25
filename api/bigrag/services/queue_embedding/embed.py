from __future__ import annotations

import math
import time

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.embedding import truncate_to_tokens

logger = get_logger("bigrag.queue")

PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)


async def embed_with_cache(
    texts: list[str],
    model,
    provider: str,
    model_name: str,
    dimension: int,
    input_type: str = "document",
) -> list[list[float]]:
    cache_texts, _ = truncate_to_tokens(texts, model_name)
    logger.debug(
        "embedding cache lookup",
        provider=provider,
        model=model_name,
        dimension=dimension,
        inputs=len(texts),
    )
    cached = await embedding_cache.get_many(
        cache_texts, model.cache_identity, dimension, input_type
    )
    missing_idx = [i for i in range(len(texts)) if i not in cached]
    logger.debug(
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
        logger.debug(
            "embedding provider request",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
        )
        fresh = await model.embed(missing_texts, input_type=input_type)
        logger.debug(
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
        for vec in fresh:
            if any(not math.isfinite(v) for v in vec):
                raise ValueError("embedding provider returned non-finite values")
        await embedding_cache.put_many(
            missing_cache_texts, fresh, model.cache_identity, dimension, input_type
        )
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
