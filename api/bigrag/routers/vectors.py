from __future__ import annotations

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request

from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.query import (
    VectorDeleteRequest,
    VectorDeleteResponse,
    VectorUpsertRequest,
    VectorUpsertResponse,
)
from bigrag.routers import get_collection_or_404
from bigrag.services import access_log
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.tenant_enforcement import require_tenant_metadata
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.vectors")

router = APIRouter(tags=["query"])


@router.post(
    "/v1/collections/{collection_name}/vectors/upsert",
    response_model=VectorUpsertResponse,
)
async def upsert_vectors(
    collection_name: str,
    body: VectorUpsertRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="vectors.upsert",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
        metadata={"vector_count": len(body.vectors)},
    )
    collection = await get_collection_or_404(collection_name)
    limits = await get_values(
        [
            "max_vector_upsert_count",
            "max_vector_text_chars",
            "max_vector_metadata_bytes",
        ]
    )
    if len(body.vectors) > limits["max_vector_upsert_count"]:
        raise HTTPException(
            status_code=413,
            detail=f"Too many vectors. Max: {limits['max_vector_upsert_count']}",
        )
    logger.info("vector upsert", collection=collection_name, vectors=len(body.vectors))

    ids = [v.id for v in body.vectors]
    embeddings = [v.embedding for v in body.vectors]
    texts = [v.text for v in body.vectors]
    metadata = [v.metadata for v in body.vectors]
    expected_dimension = int(collection.get("dimension") or 0)
    for index, vector in enumerate(body.vectors):
        if expected_dimension and len(vector.embedding) != expected_dimension:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"vectors[{index}].embedding has dimension {len(vector.embedding)}, "
                    f"expected {expected_dimension}"
                ),
            )
        if len(vector.text) > limits["max_vector_text_chars"]:
            raise HTTPException(
                status_code=413,
                detail=f"vectors[{index}].text is too large",
            )
        metadata_bytes = len(orjson.dumps(vector.metadata))
        if metadata_bytes > limits["max_vector_metadata_bytes"]:
            raise HTTPException(
                status_code=413,
                detail=f"vectors[{index}].metadata is too large",
            )
    for index, meta in enumerate(metadata):
        require_tenant_metadata(collection, meta, label=f"vectors[{index}].metadata")

    count = await vector_store.upsert(
        collection=collection_name,
        ids=ids,
        embeddings=embeddings,
        texts=texts,
        metadata=metadata,
    )
    await invalidate_collection_query_cache(collection_name)
    logger.info("vector upsert complete", collection=collection_name, upserted=count)
    access_log.set_context(request, metadata={"upserted": count})

    return VectorUpsertResponse(upserted=count)


@router.post(
    "/v1/collections/{collection_name}/vectors/delete",
    response_model=VectorDeleteResponse,
)
async def delete_vectors(
    collection_name: str,
    body: VectorDeleteRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="vectors.delete",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
        metadata={"vector_count": len(body.ids)},
    )
    limits = await get_values(["max_vector_delete_count"])
    if len(body.ids) > limits["max_vector_delete_count"]:
        raise HTTPException(
            status_code=413,
            detail=f"Too many vector IDs. Max: {limits['max_vector_delete_count']}",
        )
    await get_collection_or_404(collection_name)
    logger.info("vector delete", collection=collection_name, ids=len(body.ids))
    await vector_store.delete_by_ids(
        collection_name,
        body.ids,
    )
    await invalidate_collection_query_cache(collection_name)
    access_log.set_context(request, metadata={"deleted": len(body.ids)})
    return VectorDeleteResponse(deleted=len(body.ids))
