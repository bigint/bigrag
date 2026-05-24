from __future__ import annotations

import asyncio

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm.attributes import flag_modified

from bigrag.db.engine import session_factory
from bigrag.db.models import EmbeddingCache
from bigrag.logging import get_logger
from bigrag.services import crypto
from bigrag.services.crypto import EncryptedString

logger = get_logger("bigrag.reencrypt")

_REENCRYPT_BATCH_SIZE = 500


def _encrypted_string_columns(model: type) -> list[str]:
    mapper = sa_inspect(model)
    names: list[str] = []
    for column_property in mapper.column_attrs:
        column = column_property.columns[0]
        if isinstance(column.type, EncryptedString):
            names.append(column_property.key)
    return names


def _encrypted_string_models() -> list[type]:
    from bigrag.db.models import (
        Collection,
        ConnectorSourceCredential,
        EmbeddingPreset,
        InstanceSetting,
        Webhook,
    )

    return [
        Collection,
        ConnectorSourceCredential,
        EmbeddingPreset,
        InstanceSetting,
        Webhook,
    ]


async def _reencrypt_model(model: type) -> int:
    columns = _encrypted_string_columns(model)
    if not columns:
        return 0
    rewritten = 0
    async with session_factory()() as session:
        rows = (await session.scalars(sa.select(model))).all()
        for row in rows:
            touched = False
            for name in columns:
                value = getattr(row, name)
                if value is None:
                    continue
                setattr(row, name, value)
                flag_modified(row, name)
                touched = True
            if touched:
                rewritten += 1
        await session.commit()
    logger.info("reencrypt: rewrote rows", model=model.__name__, rows=rewritten)
    return rewritten


async def _reencrypt_embedding_cache() -> int:
    rewritten = 0
    async with session_factory()() as session:
        rows = (
            await session.execute(
                sa.select(
                    EmbeddingCache.content_hash,
                    EmbeddingCache.model_key,
                    EmbeddingCache.vector,
                )
            )
        ).all()
        for content_hash, model_key, blob in rows:
            if blob is None or not crypto.looks_encrypted_bytes(blob):
                continue
            try:
                plaintext = crypto.decrypt_bytes(blob)
            except Exception as exc:
                logger.warning(
                    "reencrypt: embedding_cache row undecryptable; skipping",
                    content_hash=content_hash,
                    model_key=model_key,
                    error=str(exc),
                )
                continue
            await session.execute(
                sa.update(EmbeddingCache)
                .where(EmbeddingCache.content_hash == content_hash)
                .where(EmbeddingCache.model_key == model_key)
                .values(vector=crypto.encrypt_bytes(plaintext))
            )
            rewritten += 1
            if rewritten % _REENCRYPT_BATCH_SIZE == 0:
                await session.commit()
        await session.commit()
    logger.info("reencrypt: rewrote embedding_cache rows", rows=rewritten)
    return rewritten


async def reencrypt_all() -> dict[str, int]:
    if not crypto.is_configured():
        raise crypto.CryptoNotConfiguredError(
            "BIGRAG_MASTER_KEY is not set; cannot re-encrypt encrypted columns."
        )
    summary: dict[str, int] = {}
    for model in _encrypted_string_models():
        summary[model.__name__] = await _reencrypt_model(model)
    summary["EmbeddingCache"] = await _reencrypt_embedding_cache()
    logger.info("reencrypt: complete", summary=summary)
    return summary


def cli() -> None:
    summary = asyncio.run(reencrypt_all())
    total = sum(summary.values())
    logger.info(
        "reencrypt: finished under current BIGRAG_MASTER_KEY",
        total=total,
        summary=summary,
    )
