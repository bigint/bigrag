from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import AccessLog
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.access import (
    AccessLogBucket,
    AccessLogEntry,
    AccessLogListResponse,
    AccessLogOverviewResponse,
    AccessLogTimelinePoint,
)
from bigrag.services.access_log import RAG_ACCESS_ACTIONS

router = APIRouter(prefix="/v1/admin/access", tags=["admin:access"])
_RAG_ACTION_FILTER = AccessLog.action.in_(tuple(sorted(RAG_ACCESS_ACTIONS)))


def _entry(row: AccessLog) -> AccessLogEntry:
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


@router.get("/logs", response_model=AccessLogListResponse)
async def list_access_logs(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    api_key_id: str | None = Query(default=None),
    auth_method: str | None = Query(default=None, max_length=30),
    collection: str | None = Query(default=None, max_length=120),
    method: str | None = Query(default=None, max_length=10),
    path: str | None = Query(default=None, max_length=300),
    status_family: str | None = Query(default=None, pattern=r"^[1-5]xx$"),
    success: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AccessLogListResponse:
    filters = [_RAG_ACTION_FILTER]
    if action:
        filters.append(AccessLog.action == action)
    if actor_id:
        try:
            filters.append(AccessLog.actor_id == uuid.UUID(actor_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid actor_id") from exc
    if api_key_id:
        try:
            filters.append(AccessLog.api_key_id == uuid.UUID(api_key_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid api_key_id") from exc
    if auth_method:
        filters.append(AccessLog.auth_method == auth_method)
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

    entries = (
        await session.scalars(
            sa.select(AccessLog)
            .where(*filters)
            .order_by(AccessLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await session.scalar(sa.select(sa.func.count()).select_from(AccessLog).where(*filters))
    return AccessLogListResponse(entries=[_entry(row) for row in entries], total=total or 0)


@router.get("/overview", response_model=AccessLogOverviewResponse)
async def access_overview(
    window_days: int = Query(default=7, ge=1, le=90),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AccessLogOverviewResponse:
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
                sa.func.count().filter(AccessLog.auth_method == "api_key").label("api_key_events"),
                sa.func.count().filter(AccessLog.action.like("query.%")).label("query_events"),
            ).where(*filters)
        )
    ).one()

    by_status_rows = (
        await session.execute(
            sa.select(AccessLog.status_code, sa.func.count().label("count"))
            .where(*filters)
            .group_by(AccessLog.status_code)
            .order_by(sa.desc("count"))
        )
    ).all()
    status_counts: dict[str, int] = {}
    for row in by_status_rows:
        label = f"{int(row.status_code) // 100}xx"
        status_counts[label] = status_counts.get(label, 0) + int(row.count)
    by_status = [
        AccessLogBucket(label=label, count=count)
        for label, count in sorted(status_counts.items(), key=lambda item: item[0])
    ]

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
    return AccessLogOverviewResponse(
        window_days=window_days,
        total_events=total,
        success_rate=round((successes / total) * 100, 2) if total else 0,
        error_rate=round((errors / total) * 100, 2) if total else 0,
        avg_latency_ms=round(float(summary.avg_latency or 0), 2),
        p95_latency_ms=round(float(summary.p95_latency or 0), 2),
        unique_users=int(summary.unique_users or 0),
        api_key_events=int(summary.api_key_events or 0),
        query_events=int(summary.query_events or 0),
        by_action=await _buckets(
            session,
            AccessLog.action,
            filters=filters,
            include_latency=False,
        ),
        by_status=by_status,
        by_auth_method=await _buckets(session, AccessLog.auth_method, filters=filters, limit=4),
        top_collections=await _buckets(
            session,
            AccessLog.collection_name,
            filters=filters,
            limit=6,
        ),
        top_paths=await _buckets(session, AccessLog.path, filters=filters, limit=6),
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
        recent=[_entry(row) for row in recent],
    )
