from __future__ import annotations

import asyncio

from bigrag.logging import get_logger

logger = get_logger("bigrag.utils")


def safe_create_task(coro, *, name: str = "background") -> asyncio.Task:

    task = asyncio.create_task(coro, name=name)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.warning(f"Background task '{name}' failed: {exc!r}")

    task.add_done_callback(_on_done)
    return task
