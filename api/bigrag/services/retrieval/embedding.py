from __future__ import annotations

from fastapi import HTTPException

from bigrag.logging import get_logger
from bigrag.services.collection_config import get_embedding_model_for
from bigrag.services.error_sanitize import safe_error_detail

logger = get_logger("bigrag.routers")


def resolve_embedding_model(collection: dict, *, error_label: str | None = None):
    try:
        return get_embedding_model_for(collection)
    except (ImportError, ValueError) as exc:
        if error_label is not None:
            raise HTTPException(
                status_code=400,
                detail=f"{error_label}: {exc}",
            ) from exc
        logger.warning(
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
