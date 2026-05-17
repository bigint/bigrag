from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AccessLogEntry(BaseModel):
    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    api_key_id: str | None = None
    api_key_name: str | None = None
    auth_method: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    collection_name: str | None = None
    method: str
    path: str
    route: str | None = None
    status_code: int
    success: bool
    latency_ms: float
    request_id: str | None = None
    metadata: dict
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AccessLogListResponse(BaseModel):
    entries: list[AccessLogEntry]
    total: int | None = None
    next_cursor: str | None = None


class AccessLogBucket(BaseModel):
    label: str
    count: int
    avg_latency_ms: float | None = None


class AccessLogTimelinePoint(BaseModel):
    bucket: datetime
    events: int
    errors: int
    avg_latency_ms: float


class AccessLogOverviewResponse(BaseModel):
    window_days: int
    total_events: int
    success_rate: float
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    unique_users: int
    query_events: int
    by_action: list[AccessLogBucket]
    latency_by_action: list[AccessLogBucket]
    timeline: list[AccessLogTimelinePoint]
    recent: list[AccessLogEntry]
