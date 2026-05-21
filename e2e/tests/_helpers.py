"""Shared helpers for the e2e test suites.

Keep this module free of fixtures or top-level imports of pytest plugins
so it can be used from non-test code (for example, the smoke runner).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


CollectionFactory = Callable[..., Awaitable[dict[str, Any]]]
DocumentFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


def unique_name(prefix: str = "e2e") -> str:
    """Return a compact unique collection name."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def read_fixture(name: str) -> bytes:
    """Return the bytes of a file in ``e2e/fixtures/documents/<name>``."""
    path = FIXTURES_DIR / "documents" / name
    if not path.exists():
        raise FileNotFoundError(f"fixture not found: {path}")
    return path.read_bytes()


def assert_envelope(response: httpx.Response, status: int) -> Any:
    """Assert ``response`` matches ``status`` and return its parsed JSON.

    Failing assertions include the full response body for fast triage.
    """
    body: Any
    try:
        body = response.json()
    except Exception:
        body = response.text
    assert response.status_code == status, (
        f"expected status {status} got {response.status_code}: {body!r}"
    )
    return body


async def poll_until(
    coro_factory: Callable[[], Awaitable[Any]],
    predicate: Callable[[Any], bool],
    *,
    timeout: float = 30.0,
    interval: float = 0.5,
    description: str = "condition",
) -> Any:
    """Poll ``coro_factory`` until ``predicate`` returns truthy or timeout.

    Returns the final value. Raises ``TimeoutError`` with the most recent
    value attached for triage.
    """
    deadline = time.monotonic() + timeout
    last_value: Any = None
    while True:
        last_value = await coro_factory()
        if predicate(last_value):
            return last_value
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"poll_until timed out waiting for {description!r}; last={last_value!r}"
            )
        await asyncio.sleep(interval)


async def seed_collection(
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
    *,
    fixtures: tuple[str, ...] = ("sample.txt", "sample.md"),
) -> dict[str, Any]:
    """Create a fresh collection and upload ``fixtures`` into it.

    Asserts every uploaded document reaches ``status == "ready"``. Returns
    the collection dict (not the document dicts) — callers that need the
    document IDs should do the uploads inline.
    """
    coll = await collection()
    for fixture in fixtures:
        doc = await document(coll["name"], fixture=fixture)
        assert doc["status"] == "ready", doc
    return coll


async def wait_until_searchable(
    client: httpx.AsyncClient,
    name: str,
    query: str,
    *,
    top_k: int = 5,
    timeout: float = 30.0,
) -> bool:
    """Poll ``POST /v1/collections/{name}/query`` until at least one hit lands.

    Returns ``True`` once the query produces results. Raises ``TimeoutError``
    via ``poll_until`` if no results appear within ``timeout`` seconds.
    """

    async def _do() -> dict[str, Any]:
        resp = await client.post(
            f"/v1/collections/{name}/query",
            json={"query": query, "top_k": top_k},
        )
        return assert_envelope(resp, 200)

    await poll_until(
        _do,
        predicate=lambda body: len(body.get("results") or []) > 0,
        timeout=timeout,
        interval=0.5,
        description=f"results for {query!r} on {name}",
    )
    return True
