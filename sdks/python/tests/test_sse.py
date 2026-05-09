from __future__ import annotations

import asyncio

import httpx

from bigrag._sse import parse_sse_stream


def run(coro):
    return asyncio.run(coro)


def stream_response(text: str) -> httpx.Response:
    request = httpx.Request("GET", "http://api.local/events")
    return httpx.Response(200, text=text, request=request)


def test_parse_sse_stream_yields_valid_data_lines() -> None:
    async def scenario() -> list[dict]:
        response = stream_response(
            ': ping\n\ndata: {"event": "progress", "data": {"progress": 0.5}}\n\n'
            "event: ignored\n"
            'data: {"event": "done", "data": {"status": "ok"}}\n\n'
        )
        events = []
        async for event in parse_sse_stream(response):
            events.append(event)
        return events

    assert run(scenario()) == [
        {"event": "progress", "data": {"progress": 0.5}},
        {"event": "done", "data": {"status": "ok"}},
    ]


def test_parse_sse_stream_skips_malformed_json() -> None:
    async def scenario() -> list[dict]:
        response = stream_response('data: nope\n\ndata: {"event": "done"}\n\n')
        events = []
        async for event in parse_sse_stream(response):
            events.append(event)
        return events

    assert run(scenario()) == [{"event": "done"}]
