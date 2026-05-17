from __future__ import annotations

import uuid

import sqlalchemy as sa
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.logging import get_logger
from bigrag.services.collection_cache import get_or_404 as get_collection_or_404
from bigrag.services.collection_config import get_embedding_model_for, get_reranking_config
from bigrag.services.error_sanitize import safe_error_detail

__all__ = [
    "ensure_embedding_or_400",
    "get_collection_or_404",
    "get_embedding_model_for",
    "get_reranking_config",
    "is_unique_violation",
    "uuid_or_404",
    "validate_collection_name",
]

_logger = get_logger("bigrag.routers")


def uuid_or_404(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{label} not found") from exc


def ensure_embedding_or_400(collection: dict):
    try:
        return get_embedding_model_for(collection)
    except (ImportError, ValueError) as exc:
        _logger.warning(
            "embedding model unavailable",
            collection=collection.get("name"),
            error=repr(exc),
        )
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(
                exc, "Embedding provider is not available for this collection."
            ),
        ) from exc


async def validate_collection_name(session: AsyncSession, collection: str | None) -> str | None:
    if collection is None:
        return None
    name = collection.strip()
    if not name:
        return None
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=400, detail=f"Collection {name!r} does not exist")
    return name


def is_unique_violation(exc: IntegrityError) -> bool:
    return isinstance(exc.orig, UniqueViolationError) or "unique" in str(exc.orig).lower()
