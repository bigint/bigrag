from __future__ import annotations

import asyncio

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import QueryLog
from bigrag.services import redis_cache


async def _period_stats(session, collection_name: str, days: int) -> dict:
    since = sa.func.now() - sa.text("make_interval(days => :d)").bindparams(d=days)
    row = (
        await session.execute(
            sa.select(
                sa.func.count().label("query_count"),
                sa.func.coalesce(sa.func.avg(QueryLog.latency_ms), 0).label("avg_latency_ms"),
                sa.func.coalesce(sa.func.avg(QueryLog.avg_score), 0).label("avg_score"),
                sa.func.coalesce(sa.func.avg(QueryLog.result_count), 0).label("avg_result_count"),
            )
            .where(QueryLog.collection_name == collection_name)
            .where(QueryLog.created_at > since)
        )
    ).one()
    return {
        "query_count": row.query_count,
        "avg_latency_ms": round(float(row.avg_latency_ms), 2),
        "avg_score": round(float(row.avg_score), 4),
        "avg_result_count": round(float(row.avg_result_count), 1),
    }


async def collection_analytics(collection_name: str) -> dict:
    cache_key = f"analytics:{collection_name}"
    cached = await redis_cache.get(cache_key)
    if cached:
        return cached

    async with session_factory()() as session:
        top_queries_rows = (
            await session.execute(
                sa.select(QueryLog.query, sa.func.count().label("count"))
                .where(QueryLog.collection_name == collection_name)
                .where(QueryLog.created_at > sa.func.now() - sa.text("make_interval(days => 7)"))
                .group_by(QueryLog.query)
                .order_by(sa.desc("count"))
                .limit(10)
            )
        ).all()

        stats_24h, stats_7d, stats_30d = await asyncio.gather(
            _period_stats(session, collection_name, 1),
            _period_stats(session, collection_name, 7),
            _period_stats(session, collection_name, 30),
        )

    result = {
        "collection": collection_name,
        "period_24h": stats_24h,
        "period_7d": stats_7d,
        "period_30d": stats_30d,
        "top_queries": [{"query": r.query, "count": r.count} for r in top_queries_rows],
    }
    await redis_cache.set(cache_key, result, ttl=300)
    return result
