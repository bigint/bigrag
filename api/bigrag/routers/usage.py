"""Usage and cost aggregation endpoint.

Aggregates from:

- ``documents.file_size`` + ``documents.chunk_count`` for storage /
  ingestion volume
- ``query_log`` for query volume and average latency
- A simple rate card (per-1M-token rates) for a rough dollar figure

The cost is approximate — providers change pricing, and we don't
track every detail (reranker calls, hypothetical HyDE calls, etc.).
For exact numbers consumers should cross-check against their
provider's billing dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user

logger = get_logger("bigrag.routers.usage")

router = APIRouter(prefix="/v1/usage", tags=["usage"])


# Rough embedding prices in USD per million tokens.
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
    # Embeddings column is a rough estimate using token_count on
    # documents, multiplied by the collection's embedding model rate.
    embedding_tokens_total: int
    embedding_cost_usd_estimate: float
    by_collection: list[dict]


@router.get("", response_model=UsageResponse)
async def get_usage(
    window_days: int = Query(default=30, ge=1, le=365),
    _: dict = Depends(get_current_user),
) -> UsageResponse:
    interval = f"{window_days} days"

    per_collection = await db.fetch(
        """
        SELECT
            c.id AS collection_id,
            c.name AS collection,
            c.embedding_model,
            COALESCE(SUM(d.file_size), 0)::bigint AS storage_bytes,
            COALESCE(SUM(d.chunk_count), 0)::bigint AS chunks,
            COUNT(d.id)::bigint AS documents,
            COALESCE(SUM(d.token_count), 0)::bigint AS embedding_tokens
        FROM collections c
        LEFT JOIN documents d ON d.collection_id = c.id
        GROUP BY c.id, c.name, c.embedding_model
        ORDER BY storage_bytes DESC
        """
    )

    query_counts = await db.fetch(
        f"""
        SELECT collection_name, COUNT(*) AS cnt, COALESCE(AVG(latency_ms), 0) AS avg_latency
        FROM query_log
        WHERE created_at > now() - interval '{interval}'
        GROUP BY collection_name
        """
    )
    queries_by_col = {r["collection_name"]: r for r in query_counts}

    by_collection = []
    queries_total = 0
    docs_total = 0
    chunks_total = 0
    bytes_total = 0
    tokens_total = 0
    cost_total = 0.0

    for row in per_collection:
        col = row["collection"]
        rate = _EMBED_RATES_USD_PER_M.get(row["embedding_model"], 0.0)
        col_tokens = int(row["embedding_tokens"])
        col_cost = col_tokens / 1_000_000 * rate
        q = queries_by_col.get(col)
        q_count = int(q["cnt"]) if q else 0
        q_avg_latency = float(q["avg_latency"]) if q else 0.0

        by_collection.append(
            {
                "collection": col,
                "documents": int(row["documents"]),
                "chunks": int(row["chunks"]),
                "storage_bytes": int(row["storage_bytes"]),
                "embedding_tokens": col_tokens,
                "embedding_cost_usd_estimate": round(col_cost, 4),
                "queries": q_count,
                "avg_latency_ms": round(q_avg_latency, 2),
            }
        )
        queries_total += q_count
        docs_total += int(row["documents"])
        chunks_total += int(row["chunks"])
        bytes_total += int(row["storage_bytes"])
        tokens_total += col_tokens
        cost_total += col_cost

    return UsageResponse(
        window_days=window_days,
        queries_total=queries_total,
        queries_per_day_avg=round(queries_total / max(1, window_days), 2),
        documents_total=docs_total,
        chunks_total=chunks_total,
        storage_bytes_total=bytes_total,
        embedding_tokens_total=tokens_total,
        embedding_cost_usd_estimate=round(cost_total, 4),
        by_collection=by_collection,
    )
