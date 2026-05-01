from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import numpy as np
import orjson

from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.semantic_cache")

SIMILARITY_THRESHOLD = 0.97
MAX_ENTRIES_PER_COLLECTION = 200
TTL_SECONDS = 60 * 30


def _list_key(collection: str) -> str:
    return f"semcache:{collection}:entries"


def _scope_hash(scope: dict[str, Any] | None) -> str:
    if not scope:
        return ""
    return hashlib.sha256(orjson.dumps(scope, option=orjson.OPT_SORT_KEYS)).hexdigest()


def _best_match(
    query_vec: list[float],
    raw_entries: list[bytes],
    threshold: float,
    now: float,
    scope_hash: str,
) -> tuple[float, dict | None]:
    if not query_vec or not raw_entries:
        return 0.0, None
    vecs: list[list[float]] = []
    payloads: list[dict] = []
    expected_dim = len(query_vec)
    for raw in raw_entries:
        try:
            entry = orjson.loads(raw)
        except (orjson.JSONDecodeError, TypeError):
            continue
        if entry.get("scope_hash", "") != scope_hash:
            continue
        if (now - entry.get("ts", 0)) > TTL_SECONDS:
            continue
        vec = entry.get("vec")
        if not vec or len(vec) != expected_dim:
            continue
        vecs.append(vec)
        payloads.append(entry.get("payload") or {})
    if not vecs:
        return 0.0, None
    mat = np.asarray(vecs, dtype=np.float32)
    q = np.asarray(query_vec, dtype=np.float32)
    qn = float(np.linalg.norm(q))
    if qn == 0:
        return 0.0, None
    norms = np.linalg.norm(mat, axis=1)
    norms[norms == 0] = 1.0
    scores = (mat @ q) / (norms * qn)
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    if best_score >= threshold:
        return best_score, payloads[best_idx]
    return best_score, None


async def lookup(
    collection: str,
    query_vec: list[float],
    *,
    scope: dict[str, Any] | None = None,
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

    score, payload = await asyncio.to_thread(
        _best_match,
        query_vec,
        raw_entries,
        threshold,
        time.time(),
        _scope_hash(scope),
    )
    if payload is not None:
        logger.info(
            "semcache: hit",
            collection=collection,
            similarity=round(score, 4),
        )
    return payload


async def store(
    collection: str,
    query_vec: list[float],
    payload: dict[str, Any],
    *,
    scope: dict[str, Any] | None = None,
) -> None:

    client = redis_cache._redis  # noqa: SLF001
    if client is None or not query_vec:
        return
    entry = {
        "vec": list(query_vec),
        "payload": payload,
        "scope_hash": _scope_hash(scope),
        "ts": time.time(),
    }
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
