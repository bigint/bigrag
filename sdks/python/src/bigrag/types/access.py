"""Access log types."""

from __future__ import annotations

from bigrag.types._compat import Any, TypedDict


class AccessLogEntry(TypedDict):
    id: str
    actor_id: str | None
    actor_email: str | None
    api_key_id: str | None
    api_key_name: str | None
    auth_method: str | None
    action: str
    resource_type: str
    resource_id: str | None
    collection_name: str | None
    method: str
    path: str
    route: str | None
    status_code: int
    success: bool
    latency_ms: float
    request_id: str | None
    metadata: dict[str, Any]
    ip: str | None
    user_agent: str | None
    created_at: str


class AccessLogListResponse(TypedDict):
    entries: list[AccessLogEntry]
    total: int


class AccessLogBucket(TypedDict):
    label: str
    count: int
    avg_latency_ms: float | None


class AccessLogTimelinePoint(TypedDict):
    bucket: str
    events: int
    errors: int
    avg_latency_ms: float


class AccessLogOverviewResponse(TypedDict):
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
