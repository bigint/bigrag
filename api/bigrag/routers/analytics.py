from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from bigrag.middleware.auth import get_current_user
from bigrag.models.query import (
    AnalyticsResponse,
    EmbeddingModelInfo,
    EmbeddingModelListResponse,
)
from bigrag.routers import enforce_collection_pin, get_collection_or_404
from bigrag.services import access_log
from bigrag.services.embedding import AVAILABLE_MODELS

router = APIRouter(tags=["query"])


@router.get("/v1/collections/{collection_name}/analytics", response_model=AnalyticsResponse)
async def collection_analytics(
    collection_name: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    enforce_collection_pin(user, collection_name)
    access_log.set_context(
        request,
        action="analytics.read",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
    )
    await get_collection_or_404(collection_name)

    from bigrag.services.analytics import collection_analytics as analytics_for

    return AnalyticsResponse(**await analytics_for(collection_name))


@router.get("/v1/embeddings/models", response_model=EmbeddingModelListResponse)
async def list_embedding_models(
    _: dict = Depends(get_current_user),
) -> EmbeddingModelListResponse:
    return EmbeddingModelListResponse(models=[EmbeddingModelInfo(**m) for m in AVAILABLE_MODELS])
