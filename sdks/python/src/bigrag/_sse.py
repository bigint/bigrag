"""Server-Sent Events (SSE) stream parser for document progress."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from bigrag._types import ProgressEvent


async def parse_sse_stream(response: httpx.Response) -> AsyncGenerator[ProgressEvent, None]:
    """Iterate over an SSE response and yield :class:`ProgressEvent` dicts.

    Lines that do not start with ``data: `` are silently skipped, as are
    lines whose JSON payload cannot be decoded.
    """
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if not payload:
            continue
        try:
            yield json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            # Skip malformed JSON
            pass
