from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import NamedTuple

import httpx

from bigrag.types.sse import ProgressEvent


class SSEFrame(NamedTuple):
    event: str
    data: str


async def parse_sse_frames(response: httpx.Response) -> AsyncGenerator[SSEFrame, None]:
    event = "message"
    data_lines: list[str] = []
    async for raw_line in response.aiter_lines():
        line = raw_line.rstrip("\r")
        if line == "":
            if data_lines:
                payload = "\n".join(data_lines)
                if payload and payload != "[DONE]":
                    yield SSEFrame(event=event, data=payload)
            event = "message"
            data_lines = []
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
        elif field == "event":
            event = value
    if data_lines:
        payload = "\n".join(data_lines)
        if payload and payload != "[DONE]":
            yield SSEFrame(event=event, data=payload)


async def parse_sse_stream(
    response: httpx.Response,
) -> AsyncGenerator[ProgressEvent, None]:
    async for frame in parse_sse_frames(response):
        try:
            yield json.loads(frame.data)
        except (json.JSONDecodeError, ValueError):
            pass
