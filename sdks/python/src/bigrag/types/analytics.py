from __future__ import annotations

from typing import TypedDict


class PeriodStats(TypedDict):
    query_count: int
    avg_latency_ms: float
    avg_score: float
    avg_result_count: float


class TopQuery(TypedDict):
    query: str
    count: int


class AnalyticsResponse(TypedDict):
    collection: str
    period_24h: PeriodStats
    period_7d: PeriodStats
    period_30d: PeriodStats
    top_queries: list[TopQuery]
