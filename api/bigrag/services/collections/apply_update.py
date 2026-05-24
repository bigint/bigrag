from __future__ import annotations

from fastapi import HTTPException

from bigrag.db.models import Collection
from bigrag.models.collection import UpdateCollectionRequest
from bigrag.services.collection_provision import verify_embedding_credentials


async def apply_collection_update(
    collection: Collection,
    body: UpdateCollectionRequest,
) -> list[str]:
    fields: list[str] = []
    if body.description is not None:
        collection.description = body.description
        fields.append("description")
    if body.metadata is not None:
        collection.meta = body.metadata
        fields.append("metadata")
    if "embedding_api_key" in body.model_fields_set:
        if body.embedding_api_key is None:
            collection.embedding_api_key = None
        else:
            new_key = body.embedding_api_key.strip()
            if not new_key:
                raise HTTPException(
                    status_code=422,
                    detail="embedding_api_key cannot be empty.",
                )
            await verify_embedding_credentials(
                collection.embedding_provider,
                new_key,
                collection.embedding_base_url,
                collection.embedding_model,
            )
            collection.embedding_api_key = new_key
        if body.embedding_api_key is not None and collection.embedding_preset_id is not None:
            collection.embedding_preset_id = None
            fields.append("embedding_preset_id")
        fields.append("embedding_api_key")
    if body.reranking_enabled is not None:
        collection.reranking_enabled = body.reranking_enabled
        fields.append("reranking_enabled")
    if body.reranking_model is not None:
        collection.reranking_model = body.reranking_model
        fields.append("reranking_model")
    if "reranking_api_key" in body.model_fields_set:
        collection.reranking_api_key = body.reranking_api_key
        fields.append("reranking_api_key")
    if body.multimodal_enabled is not None:
        collection.multimodal_enabled = body.multimodal_enabled
        fields.append("multimodal_enabled")
        if not body.multimodal_enabled and collection.multimodal_enrichment_enabled:
            collection.multimodal_enrichment_enabled = False
            fields.append("multimodal_enrichment_enabled")
    if body.multimodal_enrichment_enabled is not None:
        if body.multimodal_enrichment_enabled and not collection.multimodal_enabled:
            collection.multimodal_enabled = True
            fields.append("multimodal_enabled")
        collection.multimodal_enrichment_enabled = body.multimodal_enrichment_enabled
        fields.append("multimodal_enrichment_enabled")
    if body.default_top_k is not None:
        collection.default_top_k = body.default_top_k
        fields.append("default_top_k")
    if body.default_min_score is not None:
        collection.default_min_score = body.default_min_score
        fields.append("default_min_score")
    if body.default_search_mode is not None:
        collection.default_search_mode = body.default_search_mode
        fields.append("default_search_mode")
    if body.chunk_strategy is not None:
        collection.chunk_strategy = body.chunk_strategy
        fields.append("chunk_strategy")
    if body.metadata_schema is not None:
        collection.metadata_schema = body.metadata_schema
        fields.append("metadata_schema")
    return fields
