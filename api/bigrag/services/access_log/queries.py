from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import AccessLog
from bigrag.models.access import (
    AccessLogBucket,
    AccessLogEntry,
    AccessLogListResponse,
    AccessLogOverviewResponse,
    AccessLogTimelinePoint,
)
from bigrag.services import redis_cache
from bigrag.services.access_log.middleware import RAG_ACCESS_ACTIONS
from bigrag.services.pagination import paginate

_RAG_ACTION_FILTER = AccessLog.action.in_(tuple(sorted(RAG_ACCESS_ACTIONS)))
_ACCESS_OVERVIEW_TTL = 5


def access_log_entry(row: AccessLog) -> AccessLogEntry:
    return AccessLogEntry(
        id=str(row.id),
        actor_id=str(row.actor_id) if row.actor_id else None,
        actor_email=row.actor_email,
        api_key_id=str(row.api_key_id) if row.api_key_id else None,
        api_key_name=row.api_key_name,
        auth_method=row.auth_method,
        action=row.action,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        collection_name=row.collection_name,
        method=row.method,
        path=row.path,
        route=row.route,
        status_code=row.status_code,
        success=row.success,
        latency_ms=round(float(row.latency_ms), 2),
        request_id=row.request_id,
        metadata=row.meta or {},
        ip=row.ip,
        user_agent=row.user_agent,
        created_at=row.created_at,
    )


def _window_filter(days: int):
    window = sa.text("make_interval(days => :days)").bindparams(days=days)
    return AccessLog.created_at > sa.func.now() - window


async def _buckets(
    session: AsyncSession,
    column,
    *,
    filters: list,
    limit: int = 8,
    include_latency: bool = False,
) -> list[AccessLogBucket]:
    label = sa.func.coalesce(column, "unknown").label("label")
    columns = [label, sa.func.count().label("count")]
    if include_latency:
        columns.append(sa.func.coalesce(sa.func.avg(AccessLog.latency_ms), 0).label("avg_latency"))

    rows = (
        await session.execute(
            sa.select(*columns)
            .where(*filters)
            .group_by(label)
            .order_by(sa.desc("count"))
            .limit(limit)
        )
    ).all()
    return [
        AccessLogBucket(
            label=str(row.label),
            count=int(row.count),
            avg_latency_ms=round(float(row.avg_latency), 2) if include_latency else None,
        )
        for row in rows
    ]


async def access_logs_payload(
    session: AsyncSession,
    *,
    action: str | None,
    actor_id: str | None,
    collection: str | None,
    method: str | None,
    path: str | None,
    status_family: str | None,
    success: bool | None,
    limit: int,
    offset: int,
    cursor: str | None,
    include_total: bool,
) -> AccessLogListResponse:
    filters = [_RAG_ACTION_FILTER]
    if action:
        filters.append(AccessLog.action == action)
    if actor_id:
        try:
            filters.append(AccessLog.actor_id == uuid.UUID(actor_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid actor_id") from exc
    if collection:
        filters.append(AccessLog.collection_name == collection)
    if method:
        filters.append(AccessLog.method == method.upper())
    if path:
        filters.append(AccessLog.path.ilike(f"%{path}%"))
    if status_family:
        start = int(status_family[0]) * 100
        filters.append(AccessLog.status_code >= start)
        filters.append(AccessLog.status_code < start + 100)
    if success is not None:
        filters.append(AccessLog.success.is_(success))

    stmt = (
        sa.select(AccessLog)
        .where(*filters)
        .order_by(AccessLog.created_at.desc(), AccessLog.id.desc())
    )
    result = await paginate(
        session,
        stmt,
        created_col=AccessLog.created_at,
        id_col=AccessLog.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=(
            sa.select(sa.func.count()).select_from(AccessLog).where(*filters)
            if include_total
            else None
        ),
    )

    return AccessLogListResponse(
        entries=[access_log_entry(row) for row in result.rows],
        total=result.total,
        next_cursor=result.next_cursor,
    )


async def access_overview_payload(
    session: AsyncSession,
    *,
    window_days: int,
) -> AccessLogOverviewResponse:
    cache_key = f"access:overview:{window_days}"
    cached = await redis_cache.get(cache_key)
    if cached:
        return AccessLogOverviewResponse.model_validate(cached)

    filters = [_RAG_ACTION_FILTER, _window_filter(window_days)]

    summary = (
        await session.execute(
            sa.select(
                sa.func.count().label("total"),
                sa.func.count().filter(AccessLog.success.is_(True)).label("successes"),
                sa.func.count().filter(AccessLog.success.is_(False)).label("errors"),
                sa.func.coalesce(sa.func.avg(AccessLog.latency_ms), 0).label("avg_latency"),
                sa.func.coalesce(
                    sa.func.percentile_cont(0.95).within_group(AccessLog.latency_ms),
                    0,
                ).label("p95_latency"),
                sa.func.count(sa.distinct(AccessLog.actor_id)).label("unique_users"),
                sa.func.count().filter(AccessLog.action.like("query.%")).label("query_events"),
            ).where(*filters)
        )
    ).one()

    trunc_unit = "hour" if window_days <= 2 else "day"
    bucket_col = sa.func.date_trunc(trunc_unit, AccessLog.created_at).label("bucket")
    timeline_rows = (
        await session.execute(
            sa.select(
                bucket_col,
                sa.func.count().label("events"),
                sa.func.count().filter(AccessLog.success.is_(False)).label("errors"),
                sa.func.coalesce(sa.func.avg(AccessLog.latency_ms), 0).label("avg_latency"),
            )
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col.asc())
        )
    ).all()

    recent = (
        await session.scalars(
            sa.select(AccessLog).where(*filters).order_by(AccessLog.created_at.desc()).limit(12)
        )
    ).all()

    total = int(summary.total or 0)
    errors = int(summary.errors or 0)
    successes = int(summary.successes or 0)
    response = AccessLogOverviewResponse(
        window_days=window_days,
        total_events=total,
        success_rate=round((successes / total) * 100, 2) if total else 0,
        error_rate=round((errors / total) * 100, 2) if total else 0,
        avg_latency_ms=round(float(summary.avg_latency or 0), 2),
        p95_latency_ms=round(float(summary.p95_latency or 0), 2),
        unique_users=int(summary.unique_users or 0),
        query_events=int(summary.query_events or 0),
        by_action=await _buckets(
            session,
            AccessLog.action,
            filters=filters,
            include_latency=False,
        ),
        latency_by_action=await _buckets(
            session,
            AccessLog.action,
            filters=filters,
            limit=6,
            include_latency=True,
        ),
        timeline=[
            AccessLogTimelinePoint(
                bucket=(
                    row.bucket
                    if isinstance(row.bucket, datetime)
                    else datetime.fromisoformat(row.bucket)
                ),
                events=int(row.events),
                errors=int(row.errors),
                avg_latency_ms=round(float(row.avg_latency), 2),
            )
            for row in timeline_rows
        ],
        recent=[access_log_entry(row) for row in recent],
    )
    await redis_cache.set(cache_key, jsonable_encoder(response), ttl=_ACCESS_OVERVIEW_TTL)
    return response
