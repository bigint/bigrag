"""E2E tests for the queue stats endpoint (GET /v1/queue/stats)."""

from __future__ import annotations

import asyncio

from httpx import AsyncClient


EXPECTED_STATS = {
    "queued": 10,
    "completed": 5,
    "failed": 1,
    "pending": 2,
    "processing": 1,
}


def _patch_async_stats(mock_queue) -> None:
    """Make ``mock_queue.stats`` behave like an async property.

    The real ``IngestionQueue.stats`` is decorated with ``@property`` +
    ``async def``, so accessing it returns a coroutine.  The conftest sets
    ``mock_queue.stats`` as a plain dict, but the handler does
    ``await ingestion_queue.stats`` — awaiting a dict raises TypeError.

    We fix this by installing a real ``property`` on the *type* of the mock
    so that attribute access returns a coroutine wrapping the dict.
    """
    future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
    future.set_result(EXPECTED_STATS)
    type(mock_queue).stats = property(lambda self: future)


# ---------------------------------------------------------------------------
# GET /v1/queue/stats — happy path
# ---------------------------------------------------------------------------


async def test_queue_stats(client: AsyncClient, auth_headers: dict, mock_queue):
    _patch_async_stats(mock_queue)

    resp = await client.get("/v1/queue/stats", headers=auth_headers)
    assert resp.status_code == 200

    body = resp.json()
    assert body == EXPECTED_STATS


# ---------------------------------------------------------------------------
# GET /v1/queue/stats — authentication required
# ---------------------------------------------------------------------------


async def test_queue_stats_requires_auth(client: AsyncClient):
    resp = await client.get("/v1/queue/stats")
    assert resp.status_code == 401
