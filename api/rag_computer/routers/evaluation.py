from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rag_computer.logging import get_logger
from rag_computer.middleware.auth import get_current_user
from rag_computer.routers import (
    get_collection_or_404,
    get_embedding_model_for,
    get_reranking_config,
)
from rag_computer.services import access_log
from rag_computer.services.collection_scope import assert_collection_matches_pin
from rag_computer.services.retrieval import retrieve

logger = get_logger("rag_computer.routers.evaluation")

router = APIRouter(prefix="/v1/evaluation", tags=["evaluation"])


class EvalCase(BaseModel):
    query: str = Field(min_length=1)
    relevant_ids: list[str] = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=100)


class EvalRequest(BaseModel):
    collection: str
    cases: list[EvalCase] = Field(min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")


class EvalPerCase(BaseModel):
    query: str
    hit_ids: list[str]
    expected_ids: list[str]
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float


class EvalResponse(BaseModel):
    collection: str
    total_cases: int
    recall_at_k_avg: float
    mrr: float
    ndcg_at_k_avg: float
    per_case: list[EvalPerCase]


def _recall_at_k(hit_ids: list[str], expected: set[str]) -> float:
    if not expected:
        return 0.0
    return len(set(hit_ids) & expected) / len(expected)


def _reciprocal_rank(hit_ids: list[str], expected: set[str]) -> float:
    for idx, h in enumerate(hit_ids, start=1):
        if h in expected:
            return 1.0 / idx
    return 0.0


def _ndcg_at_k(hit_ids: list[str], expected: set[str]) -> float:
    if not expected:
        return 0.0
    dcg = 0.0
    for idx, h in enumerate(hit_ids, start=1):
        rel = 1 if h in expected else 0
        if rel:
            dcg += 1.0 / math.log2(idx + 1)
    k = len(hit_ids)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(expected), k) + 1))
    return dcg / ideal if ideal else 0.0


@router.post("", response_model=EvalResponse)
async def run_evaluation(
    body: EvalRequest,
    request: Request,
    user: dict = Depends(get_current_user),
) -> EvalResponse:
    access_log.set_context(
        request,
        action="evaluation.run",
        resource_type="collection",
        resource_id=body.collection,
        collection_name=body.collection,
        metadata={
            "case_count": len(body.cases),
            "search_mode": body.search_mode,
            "top_k": body.top_k,
            "query_hashes": [
                access_log.query_fingerprint(case.query)["query_hash"] for case in body.cases[:50]
            ],
        },
    )
    pinned = user.get("collection")
    if pinned:
        assert_collection_matches_pin(pinned, body.collection)

    collection = await get_collection_or_404(body.collection)
    try:
        embedding_model = get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    per_case: list[EvalPerCase] = []
    recall_sum = 0.0
    mrr_sum = 0.0
    ndcg_sum = 0.0

    for case in body.cases:
        outcome = await retrieve(
            collection_name=body.collection,
            query=case.query,
            embedding_model=embedding_model,
            top_k=case.top_k or body.top_k,
            search_mode=body.search_mode,
            reranking_config=get_reranking_config(collection),
        )
        hit_ids = [r.get("document_id") or r.get("id") for r in outcome.results]
        expected = set(case.relevant_ids)
        recall = _recall_at_k(hit_ids, expected)
        rr = _reciprocal_rank(hit_ids, expected)
        ndcg = _ndcg_at_k(hit_ids, expected)
        recall_sum += recall
        mrr_sum += rr
        ndcg_sum += ndcg
        per_case.append(
            EvalPerCase(
                query=case.query,
                hit_ids=hit_ids,
                expected_ids=case.relevant_ids,
                recall_at_k=round(recall, 4),
                reciprocal_rank=round(rr, 4),
                ndcg_at_k=round(ndcg, 4),
            )
        )

    n = len(body.cases)
    logger.info(
        "evaluation: complete",
        collection=body.collection,
        cases=n,
        recall=round(recall_sum / n, 4),
    )
    access_log.set_context(
        request,
        metadata={
            "recall_at_k_avg": round(recall_sum / n, 4),
            "mrr": round(mrr_sum / n, 4),
            "ndcg_at_k_avg": round(ndcg_sum / n, 4),
        },
    )
    return EvalResponse(
        collection=body.collection,
        total_cases=n,
        recall_at_k_avg=round(recall_sum / n, 4),
        mrr=round(mrr_sum / n, 4),
        ndcg_at_k_avg=round(ndcg_sum / n, 4),
        per_case=per_case,
    )
