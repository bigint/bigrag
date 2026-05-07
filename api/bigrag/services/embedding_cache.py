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


def _model_key(provider: str, model: str, dimension: int) -> str:
    return f"{provider}:{model}:{dimension}"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes, dimension: int) -> list[float]:
    return list(struct.unpack(f"<{dimension}f", blob))


def _encode_vector(vec: list[float]) -> bytes:
    return crypto.encrypt_bytes(_pack(vec))


def _decode_vector(blob: bytes, dimension: int) -> tuple[list[float] | None, bool]:
    if crypto.looks_encrypted_bytes(blob):
        try:
            return _unpack(crypto.decrypt_bytes(blob), dimension), False
        except Exception as exc:
            logger.debug("embedding_cache: decrypt failed", error=str(exc))
            return None, False
    try:
        return _unpack(blob, dimension), True
    except struct.error:
        return None, False


async def _cache_enabled() -> bool:
    try:
        values = await get_values(["embedding_cache_mode"])
    except Exception as exc:
        logger.debug("embedding_cache: mode lookup failed", error=str(exc))
        return False
    if values["embedding_cache_mode"] == "disabled":
        return False
    if crypto.is_configured():
        return True
    logger.warning("embedding_cache: BIGRAG_MASTER_KEY is not configured; cache disabled")
    return False


async def get_many(
    texts: list[str],
    provider: str,
    model: str,
    dimension: int,
) -> dict[int, list[float]]:

    if not texts:
        return {}
    if not await _cache_enabled():
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
    except Exception as exc:
        logger.debug("embedding_cache: lookup failed", error=str(exc))
        return {}

    by_hash = {r.content_hash: r.vector for r in rows}
    out: dict[int, list[float]] = {}
    legacy: dict[str, list[float]] = {}
    for i, h in enumerate(hashes):
        blob = by_hash.get(h)
        if blob is None:
            continue
        vector, needs_reencrypt = _decode_vector(blob, dimension)
        if vector is None:
            continue
        out[i] = vector
        if needs_reencrypt:
            legacy[h] = vector
    if out:
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
        except Exception as exc:
            logger.debug("embedding_cache: last_hit_at update failed", error=str(exc))
    if legacy:
        await _reencrypt_legacy_vectors(model_key, dimension, legacy)
    return out


async def _reencrypt_legacy_vectors(
    model_key: str,
    dimension: int,
    vectors_by_hash: dict[str, list[float]],
) -> None:
    try:
        async with session_factory()() as session:
            for content_hash, vector in vectors_by_hash.items():
                await session.execute(
                    sa.update(EmbeddingCache)
                    .where(EmbeddingCache.model_key == model_key)
                    .where(EmbeddingCache.content_hash == content_hash)
                    .values(vector=_encode_vector(vector), dimension=dimension)
                )
            await session.commit()
    except Exception as exc:
        logger.debug("embedding_cache: legacy reencrypt failed", error=str(exc))


async def put_many(
    texts: list[str],
    vectors: list[list[float]],
    provider: str,
    model: str,
    dimension: int,
) -> None:

    if not texts or len(texts) != len(vectors):
        return
    if not await _cache_enabled():
        return
    model_key = _model_key(provider, model, dimension)
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
        logger.debug("embedding_cache: insert failed", error=str(exc))


async def purge_all() -> int:
    try:
        async with session_factory()() as session:
            result = await session.execute(sa.delete(EmbeddingCache))
            await session.commit()
            return int(result.rowcount or 0)
    except Exception as exc:
        logger.debug("embedding_cache: purge failed", error=str(exc))
        return 0


async def purge_stale(retention_days: int) -> int:
    if retention_days <= 0:
        return await purge_all()
    try:
        async with session_factory()() as session:
            cutoff = sa.func.now() - sa.text("make_interval(days => :days)").bindparams(
                days=retention_days
            )
            result = await session.execute(
                sa.delete(EmbeddingCache).where(EmbeddingCache.last_hit_at < cutoff)
            )
            await session.commit()
            return int(result.rowcount or 0)
    except Exception as exc:
        logger.debug("embedding_cache: stale purge failed", error=str(exc))
        return 0
