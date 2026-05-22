from __future__ import annotations

import asyncio
import time

from bigrag.logging import get_logger
from bigrag.services.access_log.payload import query_fingerprint

logger = get_logger("bigrag.retrieval")

_cohere_clients: dict[tuple[str, str | None], object] = {}
_cohere_lock = asyncio.Lock()


async def _get_cohere_client(api_key: str, base_url: str | None):
    import cohere

    key = (api_key, base_url)
    client = _cohere_clients.get(key)
    if client is not None:
        return client
    async with _cohere_lock:
        client = _cohere_clients.get(key)
        if client is not None:
            return client
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = cohere.AsyncClientV2(**kwargs)
        _cohere_clients[key] = client
        return client


async def close_cohere_clients() -> None:
    clients = list(_cohere_clients.values())
    _cohere_clients.clear()
    for client in clients:
        try:
            await client.close()
        except Exception as exc:
            logger.warning("failed to close cohere client", error=repr(exc))


async def rerank_results(
    results: list[dict],
    query: str,
    model: str = "rerank-v3.5",
    api_key: str | None = None,
) -> list[dict]:
    if not results:
        return results

    try:
        import cohere  # noqa: F401
    except ImportError:
        logger.warning("cohere package not installed, skipping reranking")
        return results

    client = await _get_cohere_client(api_key or "", None)
    try:
        texts = [r.get("text", "") for r in results]
        t0 = time.monotonic()
        logger.debug(
            "rerank_start",
            model=model,
            inputs=len(texts),
            **query_fingerprint(query),
        )
        response = await asyncio.wait_for(
            client.rerank(
                query=query,
                documents=texts,
                model=model,
                top_n=len(results),
            ),
            timeout=30,
        )

        reranked = []
        for item in response.results:
            result = results[item.index].copy()
            result["score"] = round(item.relevance_score, 6)
            reranked.append(result)
        logger.debug(
            "rerank_complete",
            model=model,
            inputs=len(texts),
            elapsed=round(time.monotonic() - t0, 2),
            **query_fingerprint(query),
        )
        return reranked
    except Exception as exc:
        logger.error("reranking failed", error=repr(exc))
        return results
