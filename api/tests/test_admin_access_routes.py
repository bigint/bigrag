from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from conftest import FakeSession, user_principal

from bigrag.routers import admin_access


def _log_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "actor_id": uuid.uuid4(),
        "actor_email": "u@x.com",
        "api_key_id": None,
        "api_key_name": None,
        "auth_method": "session",
        "action": "query.collection",
        "resource_type": "collection",
        "resource_id": "docs",
        "collection_name": "docs",
        "method": "POST",
        "path": "/v1/collections/docs/query",
        "route": "/v1/collections/{name}/query",
        "status_code": 200,
        "success": True,
        "latency_ms": 12.5,
        "request_id": "rid-1",
        "meta": {},
        "ip": "127.0.0.1",
        "user_agent": "pytest",
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_access_logs_requires_admin(route_client) -> None:
    response = route_client(user=user_principal(role="member")).get("/v1/admin/access/logs")

    assert response.status_code == 403


def test_access_logs_invalid_actor_id_returns_400(route_client) -> None:
    response = route_client().get("/v1/admin/access/logs?actor_id=not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid actor_id"


def test_access_logs_supports_filters(route_client) -> None:
    rows = [_log_row(), _log_row(action="document.upload", success=False, status_code=500)]
    session = FakeSession(scalars_values=[rows], scalar_values=[2])

    response = route_client(session=session).get(
        "/v1/admin/access/logs?"
        "action=query.collection&collection=docs&method=post&path=/v1/&"
        "status_family=2xx&success=true&limit=10"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["entries"]) == 2


def test_access_overview_aggregates_summary(route_client) -> None:
    summary = SimpleNamespace(
        total=10,
        successes=8,
        errors=2,
        avg_latency=15.5,
        p95_latency=42.7,
        unique_users=3,
        query_events=5,
    )
    timeline_row = SimpleNamespace(
        bucket=datetime.now(UTC),
        events=4,
        errors=1,
        avg_latency=10.0,
    )
    by_action_row = SimpleNamespace(label="query.collection", count=7, avg_latency=11.0)
    recent_logs = [_log_row(), _log_row()]

    session = FakeSession(
        execute_values=[
            [summary],
            [timeline_row],
            [by_action_row],
            [by_action_row],
        ],
        scalars_values=[recent_logs],
    )

    response = route_client(session=session).get("/v1/admin/access/overview?window_days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 10
    assert body["success_rate"] == 80.0
    assert body["error_rate"] == 20.0
    assert len(body["recent"]) == 2


def test_access_overview_uses_cache_when_available(route_client, monkeypatch) -> None:
    cached = {
        "window_days": 7,
        "total_events": 9,
        "success_rate": 88.89,
        "error_rate": 11.11,
        "avg_latency_ms": 10,
        "p95_latency_ms": 20,
        "unique_users": 2,
        "query_events": 4,
        "by_action": [],
        "latency_by_action": [],
        "timeline": [],
        "recent": [],
    }

    class FakeRedisCache:
        async def get(self, key):
            assert key == "access:overview:7"
            return cached

        async def set(self, key, value, ttl=None):
            raise AssertionError("cache should not be written on hit")

    monkeypatch.setattr(admin_access, "redis_cache", FakeRedisCache())

    response = route_client().get("/v1/admin/access/overview?window_days=7")

    assert response.status_code == 200
    assert response.json()["total_events"] == 9


def test_access_overview_zero_division_safe(route_client) -> None:
    summary = SimpleNamespace(
        total=0,
        successes=0,
        errors=0,
        avg_latency=0,
        p95_latency=0,
        unique_users=0,
        query_events=0,
    )
    session = FakeSession(
        execute_values=[[summary], [], [], []],
        scalars_values=[[]],
    )

    response = route_client(session=session).get("/v1/admin/access/overview?window_days=2")

    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 0
    assert body["success_rate"] == 0
    assert body["error_rate"] == 0


def test_access_overview_writes_cache(route_client, monkeypatch) -> None:
    summary = SimpleNamespace(
        total=1,
        successes=1,
        errors=0,
        avg_latency=12,
        p95_latency=12,
        unique_users=1,
        query_events=1,
    )
    session = FakeSession(
        execute_values=[[summary], [], [], []],
        scalars_values=[[]],
    )
    writes = []

    class FakeRedisCache:
        async def get(self, key):
            assert key == "access:overview:7"
            return None

        async def set(self, key, value, ttl=None):
            writes.append((key, value, ttl))

    monkeypatch.setattr(admin_access, "redis_cache", FakeRedisCache())

    response = route_client(session=session).get("/v1/admin/access/overview?window_days=7")

    assert response.status_code == 200
    assert writes == [("access:overview:7", response.json(), admin_access._ACCESS_OVERVIEW_TTL)]
