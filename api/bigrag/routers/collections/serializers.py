from __future__ import annotations

from bigrag.db.models import Collection
from bigrag.models.collection import CollectionResponse


def collection_response(c: Collection) -> CollectionResponse:
    return CollectionResponse(
        id=str(c.id),
        name=c.name,
        description=c.description,
        embedding_provider=c.embedding_provider,
        embedding_model=c.embedding_model,
        dimension=c.dimension,
        chunk_size=c.chunk_size,
        chunk_overlap=c.chunk_overlap,
        chunk_strategy=c.chunk_strategy,
        tenant_field=c.tenant_field,
        has_metadata_schema=bool(c.metadata_schema),
        document_count=c.document_count,
        has_api_key=bool(c.embedding_api_key) or c.embedding_preset_id is not None,
        embedding_preset_id=str(c.embedding_preset_id) if c.embedding_preset_id else None,
        reranking_enabled=c.reranking_enabled,
        reranking_model=c.reranking_model,
        has_reranking_api_key=bool(c.reranking_api_key),
        multimodal_enabled=c.multimodal_enabled,
        multimodal_enrichment_enabled=c.multimodal_enrichment_enabled,
        default_top_k=c.default_top_k,
        default_min_score=c.default_min_score,
        default_search_mode=c.default_search_mode,
        metadata=c.meta or {},
        created_at=c.created_at,
        updated_at=c.updated_at,
    )
