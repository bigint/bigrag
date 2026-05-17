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
DOCUMENTS_DIR = FIXTURES_DIR / "documents"


def unique_name(prefix: str = "e2e") -> str:
    """Return a unique, Qdrant-safe collection name.

    Qdrant collection names are limited; we keep the prefix tiny and use
    8 hex characters of a UUID4 to stay well under any provider limit.
    """
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def read_fixture(name: str) -> bytes:
    """Return the bytes of a file in ``e2e/fixtures/documents/<name>``."""
    path = DOCUMENTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"fixture not found: {path}")
    return path.read_bytes()


def fixture_path(name: str) -> Path:
    return DOCUMENTS_DIR / name


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
