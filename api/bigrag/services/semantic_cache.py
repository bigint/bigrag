"""Semantic cache for /query.

Idempotency caches by key. Semantic caching caches by *meaning*: embed
the incoming query, cosine-compare against a bounded set of recent
queries for the same collection, and if similarity ≥ ``SIMILARITY_THRESHOLD``
replay the stored response. Huge cost win when users paraphrase each
other (chat assistants, helpdesks).

Storage layout in Redis:

- ``semcache:{collection}:entries`` — a list of JSON entries
  ``{"vec": [...], "payload": {...}, "ts": <epoch>}``. Capped at
  :data:`MAX_ENTRIES_PER_COLLECTION` via LTRIM after every write.

Entries expire after :data:`TTL_SECONDS`; we keep a per-entry timestamp
instead of per-entry TTLs because list-element TTLs aren't a thing in
Redis.

Misses and failures return ``None`` and log at debug — this is an
optimization, never a dependency.
"""

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
TTL_SECONDS = 60 * 30  # 30 minutes


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
    """Return the cached payload whose query vector is most similar to
    ``query_vec`` (if above ``threshold``), else None."""
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
            continue  # expired — drop on next write
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
    """Cache ``payload`` under the ``query_vec`` for future lookups.
    Best-effort: swallow Redis errors rather than failing the request."""
    client = redis_cache._redis  # noqa: SLF001
    if client is None or not query_vec:
        return
    entry = {"vec": list(query_vec), "payload": payload, "ts": time.time()}
    try:
        key = _list_key(collection)
        await client.lpush(key, orjson.dumps(entry))
        await client.ltrim(key, 0, MAX_ENTRIES_PER_COLLECTION - 1)
        # Whole-list TTL bounds memory even when nobody queries the
        # collection again.
        await client.expire(key, TTL_SECONDS * 2)
    except Exception as exc:  # noqa: BLE001
        logger.debug("semcache: store failed", collection=collection, error=str(exc))


async def invalidate(collection: str) -> None:
    """Drop every cached query for ``collection``. Call on ingest,
    delete, or re-embed so stale answers don't linger."""
    client = redis_cache._redis  # noqa: SLF001
    if client is None:
        return
    try:
        await client.delete(_list_key(collection))
    except Exception as exc:  # noqa: BLE001
        logger.debug("semcache: delete failed", collection=collection, error=str(exc))
