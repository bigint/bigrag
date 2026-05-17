"""Server-Sent Events (SSE) stream parser."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import httpx

from bigrag.types.sse import ProgressEvent


async def parse_sse_stream(
    response: httpx.Response,
) -> AsyncGenerator[ProgressEvent, None]:
    """Iterate over an SSE response and yield :class:`ProgressEvent` dicts.

    Lines that do not start with ``data: `` are silently skipped, as are
    lines whose JSON payload cannot be decoded.
    """
    data_lines: list[str] = []
    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if line == "":
            if not data_lines:
                continue
            payload = "\n".join(data_lines)
            data_lines = []
            if not payload:
                continue
            try:
                yield json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                pass
            continue
        if line.startswith(":"):
            continue
        if ":" in line:
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field, value = line, ""
        if field == "data":
            data_lines.append(value)
