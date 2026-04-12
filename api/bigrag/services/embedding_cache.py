"""Persistent embedding cache.

Keyed by ``(sha256(text), model_key)``. Survives restarts — the in-process
dict-based cache used by EmbeddingModel objects evaporates with the worker,
so a re-ingest or re-chunk today pays the full embedding bill again. With
this cache a content-identical chunk gets its vector for free.

Stored as raw float32 BYTEA in Postgres so one row per entry, no per-access
JSON overhead. The ``model_key`` is ``provider:model:dim`` so the same text
embedded under two models doesn't collide.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.engine import session_factory
from bigrag.db.models import EmbeddingCache
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
        async with session_factory()() as session:
            rows = (
                await session.execute(
                    sa.select(EmbeddingCache.content_hash, EmbeddingCache.vector)
                    .where(EmbeddingCache.model_key == model_key)
                    .where(EmbeddingCache.content_hash.in_(hashes))
                )
            ).all()
    except Exception as exc:  # noqa: BLE001 — cache is optional
        logger.debug("embedding_cache: lookup failed", error=str(exc))
        return {}

    by_hash = {r.content_hash: r.vector for r in rows}
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
            async with session_factory()() as session:
                await session.execute(
                    sa.update(EmbeddingCache)
                    .where(EmbeddingCache.model_key == model_key)
                    .where(EmbeddingCache.content_hash.in_(hit_hashes))
                    .values(last_hit_at=sa.func.now())
                )
                await session.commit()
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
    """Insert (or upsert) vectors for the given texts under the specified
    model."""
    if not texts or len(texts) != len(vectors):
        return
    model_key = _model_key(provider, model, dimension)
    rows = [
        {
            "content_hash": _hash(t),
            "model_key": model_key,
            "vector": _pack(v),
            "dimension": dimension,
        }
        for t, v in zip(texts, vectors, strict=False)
    ]
    stmt = pg_insert(EmbeddingCache).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmbeddingCache.content_hash, EmbeddingCache.model_key],
        set_={"last_hit_at": sa.func.now()},
    )
    try:
        async with session_factory()() as session:
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("embedding_cache: insert failed", error=str(exc))


async def prune_oldest(keep: int = 500_000) -> int:
    """Trim the cache to at most ``keep`` rows by deleting least-recently-
    used entries. Call periodically from :mod:`bigrag.services.cleanup`."""
    try:
        subq = (
            sa.select(EmbeddingCache.content_hash, EmbeddingCache.model_key)
            .order_by(EmbeddingCache.last_hit_at.asc())
            .offset(keep)
            .subquery()
        )
        async with session_factory()() as session:
            result = await session.execute(
                sa.delete(EmbeddingCache).where(
                    sa.tuple_(EmbeddingCache.content_hash, EmbeddingCache.model_key).in_(
                        sa.select(subq.c.content_hash, subq.c.model_key)
                    )
                )
            )
            await session.commit()
        return result.rowcount or 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("embedding_cache: prune failed", error=str(exc))
        return 0
