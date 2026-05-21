from __future__ import annotations

import httpx
from fastapi import HTTPException

from bigrag.logging import get_logger
from bigrag.models.collection import CreateCollectionRequest
from bigrag.services.credential_check import (
    CredentialCheckError,
    verify_provider_credentials,
)
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.services.collection_provision")


async def verify_embedding_credentials(
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str | None,
) -> None:
    if provider not in ("openai", "openai_compatible", "cohere", "voyage"):
        return
    try:
        await verify_provider_credentials(
            provider,  # type: ignore[arg-type]
            api_key,
            base_url,
            model=model,
        )
    except CredentialCheckError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Embedding provider rejected the API key: {exc.message}",
        ) from exc


def vector_store_unavailable_detail() -> str:
    return (
        "Turbopuffer is not configured. Save a turbopuffer API key in Settings "
        "before creating a collection."
    )


def ensure_vector_store_available() -> None:
    if vector_store.is_configured():
        return
    raise HTTPException(
        status_code=400,
        detail=vector_store_unavailable_detail(),
    )


async def create_vector_store_collection(
    body: CreateCollectionRequest,
    dimension: int,
) -> None:
    ensure_vector_store_available()
    try:
        await vector_store.create_collection(
            body.name,
            dimension,
            tenant_field=body.tenant_field,
        )
    except RuntimeError as e:
        message = str(e)
        if "API key is not configured" in message or "client is not connected" in message:
            raise HTTPException(
                status_code=400,
                detail=vector_store_unavailable_detail(),
            ) from e
        logger.warning(
            "vector collection create failed",
            collection=body.name,
            error_type=e.__class__.__name__,
            error=message,
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to create vector collection. Check Turbopuffer settings.",
        ) from e
    except httpx.HTTPError as e:
        logger.warning(
            "vector collection create failed",
            collection=body.name,
            error_type=e.__class__.__name__,
            error=str(e),
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to create vector collection. Check Turbopuffer settings.",
        ) from e
