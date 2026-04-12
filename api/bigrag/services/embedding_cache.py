"""Persistent embedding cache.

Keyed by ``(sha256(text), model_key)``. Survives restarts — the
in-process dict-based cache used by EmbeddingModel objects evaporates
with the worker, so a re-ingest or re-chunk today pays the full
embedding bill again. With this cache a content-identical chunk gets
its vector for free.

Stored as raw float32 BYTEA in Postgres so one row per entry, no
per-access JSON overhead. The ``model_key`` is ``provider:model:dim``
so the same text embedded under two models doesn't collide.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

from bigrag.database import db
from bigrag.logging import get_logger

logger = get_logger("bigrag.embedding_cache")


@dataclass
class CacheHit:
    vector: list[float]


def _model_key(provider: str, model: str, dimension: int) -> str:
    return f"{provider}:{model}:{dimension}"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes, dimension: int) -> list[float]:
    return list(struct.unpack(f"<{dimension}f", blob))


async def get_many(
    texts: list[str],
    provider: str,
    model: str,
    dimension: int,
) -> dict[int, list[float]]:
    """Return a mapping ``{index: vector}`` for whichever texts hit the
    cache. Missing indices are the caller's responsibility."""
    if not texts:
        return {}
    hashes = [_hash(t) for t in texts]
    model_key = _model_key(provider, model, dimension)
    try:
        rows = await db.fetch(
            """
            SELECT content_hash, vector
            FROM embedding_cache
            WHERE model_key = $1 AND content_hash = ANY($2::text[])
            """,
            model_key,
            hashes,
        )
    except Exception as exc:  # noqa: BLE001 — cache is optional
        logger.debug("embedding_cache: lookup failed", error=str(exc))
        return {}

    by_hash = {r["content_hash"]: r["vector"] for r in rows}
    out: dict[int, list[float]] = {}
    for i, h in enumerate(hashes):
        blob = by_hash.get(h)
        if blob is None:
            continue
        try:
            out[i] = _unpack(blob, dimension)
        except struct.error:
            continue  # corrupt row; fall through to re-embed
    if out:
        # Refresh last_hit_at so LRU eviction favours stale entries.
        hit_hashes = [hashes[i] for i in out]
        try:
            await db.execute(
                """
                UPDATE embedding_cache SET last_hit_at = now()
                WHERE model_key = $1 AND content_hash = ANY($2::text[])
                """,
                model_key,
                hit_hashes,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("embedding_cache: last_hit_at update failed", error=str(exc))
    return out


async def put_many(
    texts: list[str],
    vectors: list[list[float]],
    provider: str,
    model: str,
    dimension: int,
) -> None:
    """Insert (or upsert) vectors for the given texts under the
    specified model."""
    if not texts or len(texts) != len(vectors):
        return
    model_key = _model_key(provider, model, dimension)
    rows = [
        (_hash(t), model_key, _pack(v), dimension)
        for t, v in zip(texts, vectors, strict=False)
    ]
    try:
        await db.executemany(
            """
            INSERT INTO embedding_cache (content_hash, model_key, vector, dimension)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (content_hash, model_key) DO UPDATE
                SET last_hit_at = now()
            """,
            rows,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("embedding_cache: insert failed", error=str(exc))


async def prune_oldest(keep: int = 500_000) -> int:
    """Trim the cache to at most ``keep`` rows by deleting least-recently-
    used entries. Call periodically from :mod:`bigrag.services.cleanup`."""
    try:
        result = await db.execute(
            """
            DELETE FROM embedding_cache
            WHERE ctid IN (
                SELECT ctid FROM embedding_cache
                ORDER BY last_hit_at ASC
                OFFSET $1
            )
            """,
            keep,
        )
        # asyncpg returns "DELETE <n>"
        try:
            return int(result.split()[-1])
        except (ValueError, AttributeError):
            return 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_cache: prune failed", error=str(exc))
        return 0
