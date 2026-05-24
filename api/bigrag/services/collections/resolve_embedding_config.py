from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import EmbeddingPreset
from bigrag.logging import get_logger
from bigrag.models.collection import CreateCollectionRequest
from bigrag.services.collection_provision import verify_embedding_credentials
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.routers.collections")


@dataclass
class ResolvedEmbeddingConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None
    dimension: int
    preset: EmbeddingPreset | None


async def resolve_embedding_config(
    session: AsyncSession,
    body: CreateCollectionRequest,
) -> ResolvedEmbeddingConfig:
    preset: EmbeddingPreset | None = None
    if body.embedding_preset_id:
        try:
            preset_uuid = UUID(body.embedding_preset_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid embedding_preset_id") from e
        preset = await session.get(EmbeddingPreset, preset_uuid)
        if preset is None:
            raise HTTPException(status_code=400, detail="Embedding preset not found")

    defaults = await get_values(
        [
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "embedding_base_url",
            "embedding_api_key",
        ]
    )
    provider = (
        body.embedding_provider
        or (preset.provider if preset else None)
        or defaults["embedding_provider"]
    )
    model = (
        body.embedding_model or (preset.model if preset else None) or defaults["embedding_model"]
    )

    if provider not in ("openai", "openai_compatible", "cohere", "voyage"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported embedding provider: '{provider}'. "
                f"Supported: openai, openai_compatible, cohere, voyage"
            ),
        )
    if provider == "openai_compatible":
        has_base_url = bool(
            body.embedding_base_url
            or (preset and preset.base_url)
            or defaults["embedding_base_url"]
        )
        if not has_base_url:
            raise HTTPException(
                status_code=400,
                detail=("embedding_base_url is required when provider='openai_compatible'"),
            )
        if body.dimension is None and not (preset and preset.dimension):
            raise HTTPException(
                status_code=400,
                detail=(
                    "dimension is required when provider='openai_compatible' "
                    "— set it to the output size of your endpoint's model"
                ),
            )

    api_key = (
        body.embedding_api_key
        or (preset.api_key if preset else None)
        or defaults["embedding_api_key"]
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )
    base_url = (
        body.embedding_base_url
        or (preset.base_url if preset else None)
        or defaults["embedding_base_url"]
    )
    dimension_override = (
        body.dimension or (preset.dimension if preset else None) or defaults["embedding_dimension"]
    )

    await verify_embedding_credentials(provider, api_key, base_url, model)
    try:
        from bigrag.services.embedding import get_embedding_model

        emb = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=dimension_override,
            api_key=api_key,
            base_url=base_url,
        )
        dimension = dimension_override or emb.dimension
    except (ImportError, ValueError) as e:
        logger.warning("embedding model unavailable", error=repr(e))
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(e, "Embedding provider is not available."),
        ) from e

    return ResolvedEmbeddingConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        dimension=dimension,
        preset=preset,
    )
