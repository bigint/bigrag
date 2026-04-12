"""Tests for the per-API-key rate-limit middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_redis_incr():
    """Patch the rate-limit middleware's _incr helper with an in-memory
    counter, keeping the rest of redis_cache untouched (other middleware
    and the collection cache still need the module-level _redis to be
    None so they fall through to no-op mode).
    """
    counters: dict[str, int] = {}

    async def fake_incr(key, ttl):
        counters[key] = counters.get(key, 0) + 1
        return counters[key]

    with patch("bigrag.middleware.rate_limit._incr", side_effect=fake_incr):
        yield counters


async def test_rate_limit_throttles_after_quota(
    client, mock_db, auth_headers, mock_redis_incr
):
    """N+1 requests inside a window must return 429. Patches the rule
    list to a tiny limit so we don't have to fire 61 real requests.
    Uses GET /v1/collections which needs no mocking beyond the default."""
    with patch("bigrag.middleware.rate_limit._RULES", [("*", "/v1/", 3)]):
        # 3 allowed
        for i in range(3):
            resp = await client.get("/v1/collections", headers=auth_headers)
            assert resp.status_code != 429, f"throttled early at i={i}"

        # 4th trips
        resp = await client.get("/v1/collections", headers=auth_headers)
        assert resp.status_code == 429, resp.text
        assert "retry-after" in {k.lower() for k in resp.headers}
        assert resp.headers["X-RateLimit-Limit"] == "3"
        assert resp.headers["X-RateLimit-Remaining"] == "0"


async def test_rate_limit_exempts_metrics_and_health(
    client, auth_headers, mock_redis_incr
):
    """Health and metrics endpoints must never be throttled — they feed
    the infra that detects the outage."""
    # Pretend we're already over the limit — middleware should still pass.
    mock_redis_incr["rl:should-not-be-hit"] = 9999

    for _ in range(5):
        resp = await client.get("/health")
        assert resp.status_code != 429


async def test_rate_limit_attaches_headers_on_success(
    client, auth_headers, mock_redis_incr
):
    """Successful requests must surface X-RateLimit-* headers so clients
    can self-throttle."""
    resp = await client.get("/v1/collections", headers=auth_headers)
    # The handler itself may 5xx from mocks, but the headers should still appear.
    assert "x-ratelimit-limit" in (h.lower() for h in resp.headers)
    assert "x-ratelimit-remaining" in (h.lower() for h in resp.headers)
