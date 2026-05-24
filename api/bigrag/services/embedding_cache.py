from __future__ import annotations

import hashlib
import struct

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.engine import session_factory
from bigrag.db.models import EmbeddingCache
from bigrag.logging import get_logger
from bigrag.services import crypto
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.embedding_cache")

_LAST_HIT_REFRESH_SECONDS = 3600


def _model_key(cache_identity: str, input_type: str = "document") -> str:
    return f"{cache_identity}:{input_type}"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes, dimension: int) -> list[float]:
    if len(blob) != dimension * 4:
        raise ValueError(
            f"embedding_cache: blob length {len(blob)} does not match dimension {dimension}"
        )
    return list(struct.unpack(f"<{dimension}f", blob))


def _encode_vector(vec: list[float]) -> bytes:
    return crypto.encrypt_bytes(_pack(vec))


def _decode_vector(blob: bytes, dimension: int) -> list[float] | None:
    if not crypto.looks_encrypted_bytes(blob):
        return None
    try:
        return _unpack(crypto.decrypt_bytes(blob), dimension)
    except Exception as exc:
        logger.warning("embedding_cache: decrypt failed", error=str(exc))
        return None


async def _cache_enabled() -> bool:
    try:
        values = await get_values(["embedding_cache_mode"])
    except Exception as exc:
        logger.warning("embedding_cache: mode lookup failed", error=str(exc))
        return False
    if values["embedding_cache_mode"] == "disabled":
        return False
    if crypto.is_configured():
        return True
    logger.warning("embedding_cache: BIGRAG_MASTER_KEY is not configured; cache disabled")
    return False


async def get_many(
    texts: list[str],
    cache_identity: str,
    dimension: int,
    input_type: str = "document",
) -> dict[int, list[float]]:

    if not texts:
        return {}
    if not await _cache_enabled():
        return {}
    hashes = [_hash(t) for t in texts]
    model_key = _model_key(cache_identity, input_type)
    try:
        async with session_factory()() as session:
            rows = (
                await session.execute(
                    sa.select(EmbeddingCache.content_hash, EmbeddingCache.vector)
                    .where(EmbeddingCache.model_key == model_key)
                    .where(EmbeddingCache.content_hash.in_(hashes))
                )
            ).all()
            by_hash = {r.content_hash: r.vector for r in rows}
            out: dict[int, list[float]] = {}
            for i, h in enumerate(hashes):
                blob = by_hash.get(h)
                if blob is None:
                    continue
                vector = _decode_vector(blob, dimension)
                if vector is None:
                    continue
                out[i] = vector
            if out:
                hit_hashes = [hashes[i] for i in out]
                stale = sa.func.now() - sa.text("make_interval(secs => :secs)").bindparams(
                    secs=_LAST_HIT_REFRESH_SECONDS
                )
                await session.execute(
                    sa.update(EmbeddingCache)
                    .where(EmbeddingCache.model_key == model_key)
                    .where(EmbeddingCache.content_hash.in_(hit_hashes))
                    .where(EmbeddingCache.last_hit_at < stale)
                    .values(last_hit_at=sa.func.now())
                )
                await session.commit()
            return out
    except Exception as exc:
        logger.warning("embedding_cache: lookup failed", error=str(exc))
        return {}


async def put_many(
    texts: list[str],
    vectors: list[list[float]],
    cache_identity: str,
    dimension: int,
    input_type: str = "document",
) -> None:

    if not texts or len(texts) != len(vectors):
        return
    if not await _cache_enabled():
        return
    model_key = _model_key(cache_identity, input_type)
    rows = [
        {
            "content_hash": _hash(t),
            "model_key": model_key,
            "vector": _encode_vector(v),
            "dimension": dimension,
        }
        for t, v in zip(texts, vectors, strict=False)
    ]
    stmt = pg_insert(EmbeddingCache).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[EmbeddingCache.content_hash, EmbeddingCache.model_key],
        set_={
            "vector": stmt.excluded.vector,
            "dimension": stmt.excluded.dimension,
            "last_hit_at": sa.func.now(),
        },
    )
    try:
        async with session_factory()() as session:
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:
        logger.warning("embedding_cache: insert failed", error=str(exc))


async def purge_all() -> int:
    async with session_factory()() as session:
        result = await session.execute(sa.delete(EmbeddingCache))
        await session.commit()
        return int(result.rowcount or 0)


async def purge_to_row_limit(max_rows: int) -> int:
    if max_rows <= 0:
        return 0
    async with session_factory()() as session:
        total = await session.scalar(sa.select(sa.func.count()).select_from(EmbeddingCache)) or 0
        if total <= max_rows:
            return 0
        cutoff = await session.scalar(
            sa.select(EmbeddingCache.last_hit_at)
            .order_by(EmbeddingCache.last_hit_at.desc())
            .offset(max_rows - 1)
            .limit(1)
        )
        if cutoff is None:
            return 0
        result = await session.execute(
            sa.delete(EmbeddingCache).where(EmbeddingCache.last_hit_at < cutoff)
        )
        await session.commit()
        return int(result.rowcount or 0)


async def purge_stale(retention_days: int) -> int:
    if retention_days <= 0:
        return await purge_all()
    async with session_factory()() as session:
        cutoff = sa.func.now() - sa.text("make_interval(days => :days)").bindparams(
            days=retention_days
        )
        result = await session.execute(
            sa.delete(EmbeddingCache).where(EmbeddingCache.last_hit_at < cutoff)
        )
        await session.commit()
        return int(result.rowcount or 0)
