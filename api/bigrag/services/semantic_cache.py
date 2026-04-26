from __future__ import annotations

import math
import time
from typing import Any

import orjson

from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.semantic_cache")

SIMILARITY_THRESHOLD = 0.97
MAX_ENTRIES_PER_COLLECTION = 200
TTL_SECONDS = 60 * 30


def _list_key(collection: str) -> str:
    return f"semcache:{collection}:entries"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


async def lookup(
    collection: str,
    query_vec: list[float],
    threshold: float = SIMILARITY_THRESHOLD,
) -> dict[str, Any] | None:

    client = redis_cache._redis  # noqa: SLF001 — intentional reuse
    if client is None or not query_vec:
        return None
    try:
        raw_entries = await client.lrange(_list_key(collection), 0, -1)
    except Exception as exc:  # noqa: BLE001 — cache is optional
        logger.debug("semcache: lrange failed", collection=collection, error=str(exc))
        return None

    now = time.time()
    best_score = 0.0
    best_payload: dict | None = None
    kept: list[bytes] = []

    for raw in raw_entries:
        try:
            entry = orjson.loads(raw)
        except Exception:  # noqa: BLE001 — malformed entry; skip
            continue
        if (now - entry.get("ts", 0)) > TTL_SECONDS:
            continue
        kept.append(raw)
        score = _cosine(query_vec, entry.get("vec") or [])
        if score > best_score:
            best_score = score
            best_payload = entry.get("payload")

    if best_payload and best_score >= threshold:
        logger.info(
            "semcache: hit",
            collection=collection,
            similarity=round(best_score, 4),
        )
        return best_payload
    return None


async def store(
    collection: str,
    query_vec: list[float],
    payload: dict[str, Any],
) -> None:

    client = redis_cache._redis  # noqa: SLF001
    if client is None or not query_vec:
        return
    entry = {"vec": list(query_vec), "payload": payload, "ts": time.time()}
    try:
        key = _list_key(collection)
        await client.lpush(key, orjson.dumps(entry))
        await client.ltrim(key, 0, MAX_ENTRIES_PER_COLLECTION - 1)
        await client.expire(key, TTL_SECONDS * 2)
    except Exception as exc:  # noqa: BLE001
        logger.debug("semcache: store failed", collection=collection, error=str(exc))


async def invalidate(collection: str) -> None:

    client = redis_cache._redis  # noqa: SLF001
    if client is None:
        return
    try:
        await client.delete(_list_key(collection))
    except Exception as exc:  # noqa: BLE001
        logger.debug("semcache: delete failed", collection=collection, error=str(exc))
