from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from bigrag.config import settings

logger = logging.getLogger("bigrag.routers.query")
from bigrag.middleware.auth import get_current_user
from bigrag.routers import get_collection_or_404
from bigrag.models.query import (
    EmbeddingModelInfo,
    MultiQueryRequest,
    MultiQueryResponse,
    MultiQueryResult,
    QueryRequest,
    QueryResponse,
    QueryResult,
    VectorDeleteRequest,
    VectorUpsertRequest,
)
from bigrag.services.embedding import AVAILABLE_MODELS, get_embedding_model
from bigrag.services.retrieval import retrieve, retrieve_multi
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
    logger.info(f"query: collection={collection_name} q={body.query!r:.80s} top_k={body.top_k} filters={body.filters}")

    try:
        embedding_model = get_embedding_model(
            provider=collection["embedding_provider"],
            model_name=collection["embedding_model"],
            dimension=collection["dimension"],
            api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
        )
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    reranking_config = {
        "enabled": collection.get("reranking_enabled", False),
        "model": collection.get("reranking_model", "rerank-v3.5"),
        "api_key": collection.get("reranking_api_key") or settings.embedding_api_key,
    }

    results = await retrieve(
        collection_name=collection_name,
        query=body.query,
        embedding_model=embedding_model,
        top_k=body.top_k,
        filters=body.filters,
        min_score=body.min_score,
        search_mode=body.search_mode,
        reranking_config=reranking_config,
        rerank_override=body.rerank,
    )

    logger.info(f"query: collection={collection_name} results={len(results)}")
    return QueryResponse(
        results=[QueryResult(**r) for r in results],
        query=body.query,
        collection=collection_name,
        total=len(results),
    )


@router.post("/v1/query", response_model=MultiQueryResponse)
async def multi_collection_query(
    body: MultiQueryRequest,
    _: dict = Depends(get_current_user),
):
    logger.info(f"multi-query: collections={body.collections} q={body.query!r:.80s} top_k={body.top_k}")

    # Load all collections and their embedding models
    embedding_models = {}
    reranking_configs = {}
    for col_name in body.collections:
        collection = await _get_collection(col_name)
        try:
            embedding_models[col_name] = get_embedding_model(
                provider=collection["embedding_provider"],
                model_name=collection["embedding_model"],
                dimension=collection["dimension"],
                api_key=collection.get("embedding_api_key") or settings.embedding_api_key,
            )
        except (ImportError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Collection '{col_name}': {e}")
        reranking_configs[col_name] = {
            "enabled": collection.get("reranking_enabled", False),
            "model": collection.get("reranking_model", "rerank-v3.5"),
            "api_key": collection.get("reranking_api_key") or settings.embedding_api_key,
        }

    results = await retrieve_multi(
        collection_names=body.collections,
        query=body.query,
        embedding_models=embedding_models,
        top_k=body.top_k,
        filters=body.filters,
        min_score=body.min_score,
        search_mode=body.search_mode,
        reranking_configs=reranking_configs,
        rerank_override=body.rerank,
    )

    logger.info(f"multi-query: collections={body.collections} results={len(results)}")
    return MultiQueryResponse(
        results=[MultiQueryResult(**r) for r in results],
        query=body.query,
        collections=body.collections,
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
    logger.info(f"upsert: collection={collection_name} vectors={len(body.vectors)}")

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
    logger.info(f"upsert: collection={collection_name} upserted={count}")

    return {"status": "ok", "upserted": count}


@router.post("/v1/collections/{collection_name}/vectors/delete")
async def delete_vectors(
    collection_name: str,
    body: VectorDeleteRequest,
    _: dict = Depends(get_current_user),
):
    await _get_collection(collection_name)
    logger.info(f"vectors/delete: collection={collection_name} ids={len(body.ids)}")
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
