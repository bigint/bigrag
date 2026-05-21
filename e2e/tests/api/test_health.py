"""End-to-end tests for bigrag.routers.health.

Endpoints covered:
- GET /health             (liveness, no auth)
- GET /health/ready       (readiness, no auth, dependency breakdown)
- GET /v1/stats           (platform stats, requires auth)
"""

from __future__ import annotations

import httpx

from tests._helpers import assert_envelope


async def test_health_liveness_is_unauthenticated(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/health")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert "version" in body and isinstance(body["version"], str) and body["version"]


async def test_health_readiness_reports_each_dependency(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/health/ready")
    assert resp.status_code in (200, 503), resp.text
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    for dep in ("postgres", "redis", "vector_store", "embedding"):
        assert dep in body, f"missing dependency key {dep!r} in {body!r}"
        assert isinstance(body[dep], bool)
    assert "vector_store_provider" in body
    assert body["vector_store_provider"] == "turbopuffer"
    assert "turbopuffer" in body
    assert "qdrant" not in body


async def test_health_readiness_status_matches_http_code(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/health/ready")
    body = resp.json()
    if body["status"] == "ok":
        assert resp.status_code == 200
    else:
        assert resp.status_code == 503


async def test_platform_stats_requires_auth(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/stats")
    assert resp.status_code == 401, resp.text


async def test_platform_stats_returns_shape(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get("/v1/stats")
    body = assert_envelope(resp, 200)
    for key in (
        "status",
        "collections",
        "documents",
        "webhooks",
        "queue",
        "queue_health",
        "workers",
    ):
        assert key in body, f"missing key {key!r} in {body!r}"
    docs = body["documents"]
    for key in (
        "total",
        "ready",
        "pending",
        "processing",
        "failed",
        "total_chunks",
        "total_tokens",
        "total_size_bytes",
    ):
        assert key in docs, f"missing documents.{key} in {docs!r}"
    assert "status" in body["queue_health"]
    assert "reasons" in body["queue_health"]
    workers = body["workers"]
    for key in ("online", "status", "heartbeat_at", "heartbeat_age_seconds"):
        assert key in workers
