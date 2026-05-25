from __future__ import annotations

from typing import TypedDict


class CollectionUsage(TypedDict):
    collection: str
    documents: int
    chunks: int
    storage_bytes: int
    embedding_tokens: int
    embedding_cost_usd_estimate: float
    queries: int
    avg_latency_ms: float


class UsageResponse(TypedDict):
    window_days: int
    queries_total: int
    queries_per_day_avg: float
    documents_total: int
    chunks_total: int
    storage_bytes_total: int
    embedding_tokens_total: int
    embedding_cost_usd_estimate: float
    avg_latency_ms: float
    timeline: list[dict[str, int | float | str]]
    by_collection: list[CollectionUsage]
