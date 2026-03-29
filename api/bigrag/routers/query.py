from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bigrag.config import settings
from bigrag.middleware.auth import get_current_user
from bigrag.routers import get_collection_or_404
from bigrag.models.query import (
    EmbeddingModelInfo,
    QueryRequest,
    QueryResponse,
    QueryResult,
    VectorDeleteRequest,
    VectorUpsertRequest,
)
from bigrag.services.embedding import AVAILABLE_MODELS, get_embedding_model
from bigrag.services.retrieval import retrieve
from bigrag.services.vector_store import vector_store

router = APIRouter(tags=["query"])


_get_collection = get_collection_or_404


@router.post("/v1/collections/{collection_name}/query", response_model=QueryResponse)
async def query_collection(
    collection_name: str,
    body: QueryRequest,
    _: dict = Depends(get_current_user),
):
    collection = await _get_collection(collection_name)

    try:
        embedding_model = get_embedding_model(
            provider=collection["embedding_provider"],
            model_name=collection["embedding_model"],
            dimension=collection["dimension"],
            api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
            base_url=collection.get("embedding_base_url") or settings.embedding_base_url,
        )
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    results = await retrieve(
        collection_name=collection_name,
        query=body.query,
        embedding_model=embedding_model,
        top_k=body.top_k,
        filters=body.filters,
        min_score=body.min_score,
    )

    return QueryResponse(
        results=[QueryResult(**r) for r in results],
        query=body.query,
        collection=collection_name,
        total=len(results),
    )


# Direct vector operations (for advanced users bringing their own embeddings)


@router.post("/v1/collections/{collection_name}/vectors/upsert")
async def upsert_vectors(
    collection_name: str,
    body: VectorUpsertRequest,
    _: dict = Depends(get_current_user),
):
    await _get_collection(collection_name)

    ids = [v.id for v in body.vectors]
    embeddings = [v.embedding for v in body.vectors]
    texts = [v.text for v in body.vectors]
    metadata = [v.metadata for v in body.vectors]

    count = await vector_store.upsert(
        collection=collection_name,
        ids=ids,
        embeddings=embeddings,
        texts=texts,
        metadata=metadata,
    )

    return {"status": "ok", "upserted": count}


@router.post("/v1/collections/{collection_name}/vectors/delete")
async def delete_vectors(
    collection_name: str,
    body: VectorDeleteRequest,
    _: dict = Depends(get_current_user),
):
    await _get_collection(collection_name)
    await vector_store.delete_by_ids(collection_name, body.ids)
    return {"status": "ok", "deleted": len(body.ids)}


# Embedding model info


@router.get("/v1/embeddings/models")
async def list_embedding_models(_: dict = Depends(get_current_user)):
    return {
        "models": [
            EmbeddingModelInfo(**m).model_dump() for m in AVAILABLE_MODELS
        ]
    }
