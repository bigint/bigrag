"""E2E tests for the health and readiness endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from bigrag import __version__


# ---------------------------------------------------------------------------
# GET /health — basic liveness
# ---------------------------------------------------------------------------


async def test_health_returns_ok(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


async def test_health_requires_no_auth(client: AsyncClient):
    """Endpoint must succeed without any Authorization header."""
    resp = await client.get("/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /health/ready — readiness (all services healthy)
# ---------------------------------------------------------------------------


async def test_readiness_all_healthy(client: AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["postgres"] is True
    assert body["milvus"] is True
    assert body["redis"] is True


async def test_readiness_requires_no_auth(client: AsyncClient):
    """Readiness endpoint must succeed without any Authorization header."""
    resp = await client.get("/health/ready")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /health/ready — degraded (postgres down)
# ---------------------------------------------------------------------------


async def test_readiness_degraded_when_postgres_down(
    client: AsyncClient,
    mock_db,
):
    mock_db.fetchrow.side_effect = Exception("connection refused")

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["postgres"] is False
    # Other services should still report healthy
    assert body["milvus"] is True
    assert body["redis"] is True


# ---------------------------------------------------------------------------
# GET /health/ready — degraded (milvus down)
# ---------------------------------------------------------------------------


async def test_readiness_degraded_when_milvus_down(
    client: AsyncClient,
    mock_vector_store,
):
    mock_vector_store.client = None

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["milvus"] is False
    assert body["postgres"] is True
    assert body["redis"] is True


# ---------------------------------------------------------------------------
# GET /health/ready — degraded (redis down)
# ---------------------------------------------------------------------------


async def test_readiness_degraded_when_redis_down(
    client: AsyncClient,
    mock_queue,
):
    mock_queue._redis.ping.side_effect = Exception("redis unreachable")

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["redis"] is False
    assert body["postgres"] is True
    assert body["milvus"] is True


# ---------------------------------------------------------------------------
# GET /health/ready — degraded (all services down)
# ---------------------------------------------------------------------------


async def test_readiness_degraded_when_all_services_down(
    client: AsyncClient,
    mock_db,
    mock_vector_store,
    mock_queue,
):
    mock_db.fetchrow.side_effect = Exception("connection refused")
    mock_vector_store.client = None
    mock_queue._redis.ping.side_effect = Exception("redis unreachable")

    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["postgres"] is False
    assert body["milvus"] is False
    assert body["redis"] is False
