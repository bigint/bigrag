from __future__ import annotations

from typing import NotRequired, TypedDict

from .query import SearchMode


class EvalCase(TypedDict):
    query: str
    relevant_ids: list[str]
    top_k: NotRequired[int | None]


class EvalBody(TypedDict):
    collection: str
    cases: list[EvalCase]
    top_k: NotRequired[int]
    search_mode: NotRequired[SearchMode]


class EvalPerCase(TypedDict):
    query: str
    hit_ids: list[str]
    expected_ids: list[str]
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float


class EvalResponse(TypedDict):
    collection: str
    total_cases: int
    recall_at_k_avg: float
    mrr: float
    ndcg_at_k_avg: float
    per_case: list[EvalPerCase]
