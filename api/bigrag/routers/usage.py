from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document, QueryLog
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user

logger = get_logger("bigrag.routers.usage")

router = APIRouter(prefix="/v1/usage", tags=["usage"])


_EMBED_RATES_USD_PER_M: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
    "embed-english-v3.0": 0.10,
    "embed-multilingual-v3.0": 0.10,
    "embed-english-light-v3.0": 0.02,
    "embed-multilingual-light-v3.0": 0.02,
}


class UsageResponse(BaseModel):
    window_days: int
    queries_total: int
    queries_per_day_avg: float
    documents_total: int
    chunks_total: int
    storage_bytes_total: int
    embedding_tokens_total: int
    embedding_cost_usd_estimate: float
    avg_latency_ms: float
    timeline: list[dict]
    by_collection: list[dict]


@router.get("", response_model=UsageResponse)
async def get_usage(
    window_days: int = Query(default=30, ge=1, le=365),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UsageResponse:
    per_collection = (
        await session.execute(
            sa.select(
                Collection.id.label("collection_id"),
                Collection.name.label("collection"),
                Collection.embedding_model,
                sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("storage_bytes"),
                sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("chunks"),
                sa.func.count(Document.id).label("documents"),
                sa.func.coalesce(sa.func.sum(Document.token_count), 0).label("embedding_tokens"),
            )
            .select_from(Collection)
            .outerjoin(Document, Document.collection_id == Collection.id)
            .group_by(Collection.id, Collection.name, Collection.embedding_model)
            .order_by(sa.desc("storage_bytes"))
        )
    ).all()

    window = sa.text("make_interval(days => :days)").bindparams(days=window_days)
    query_counts = (
        await session.execute(
            sa.select(
                QueryLog.collection_name,
                sa.func.count().label("cnt"),
                sa.func.coalesce(sa.func.avg(QueryLog.latency_ms), 0).label("avg_latency"),
            )
            .where(QueryLog.created_at > sa.func.now() - window)
            .group_by(QueryLog.collection_name)
        )
    ).all()
    queries_by_col = {r.collection_name: r for r in query_counts}
    timeline_rows = (
        await session.execute(
            sa.select(
                sa.func.date_trunc("day", QueryLog.created_at).label("bucket"),
                sa.func.count().label("queries"),
                sa.func.coalesce(sa.func.avg(QueryLog.latency_ms), 0).label("avg_latency"),
            )
            .where(QueryLog.created_at > sa.func.now() - window)
            .group_by("bucket")
            .order_by("bucket")
        )
    ).all()
    timeline = [
        {
            "date": row.bucket.isoformat(),
            "queries": int(row.queries),
            "avg_latency_ms": round(float(row.avg_latency), 2),
        }
        for row in timeline_rows
    ]

    by_collection: list[dict] = []
    queries_total = 0
    docs_total = 0
    chunks_total = 0
    bytes_total = 0
    tokens_total = 0
    cost_total = 0.0

    for row in per_collection:
        rate = _EMBED_RATES_USD_PER_M.get(row.embedding_model, 0.0)
        col_tokens = int(row.embedding_tokens)
        col_cost = col_tokens / 1_000_000 * rate
        q = queries_by_col.get(row.collection)
        q_count = int(q.cnt) if q else 0
        q_avg_latency = float(q.avg_latency) if q else 0.0

        by_collection.append(
            {
                "collection": row.collection,
                "documents": int(row.documents),
                "chunks": int(row.chunks),
                "storage_bytes": int(row.storage_bytes),
                "embedding_tokens": col_tokens,
                "embedding_cost_usd_estimate": round(col_cost, 4),
                "queries": q_count,
                "avg_latency_ms": round(q_avg_latency, 2),
            }
        )
        queries_total += q_count
        docs_total += int(row.documents)
        chunks_total += int(row.chunks)
        bytes_total += int(row.storage_bytes)
        tokens_total += col_tokens
        cost_total += col_cost
    avg_latency = (
        sum(item["queries"] * item["avg_latency_ms"] for item in by_collection) / queries_total
        if queries_total
        else 0.0
    )

    return UsageResponse(
        window_days=window_days,
        queries_total=queries_total,
        queries_per_day_avg=round(queries_total / max(1, window_days), 2),
        documents_total=docs_total,
        chunks_total=chunks_total,
        storage_bytes_total=bytes_total,
        embedding_tokens_total=tokens_total,
        embedding_cost_usd_estimate=round(cost_total, 4),
        avg_latency_ms=round(avg_latency, 2),
        timeline=timeline,
        by_collection=by_collection,
    )
