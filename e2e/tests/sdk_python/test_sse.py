from __future__ import annotations

import httpx
from bigrag._sse import parse_sse_frames, parse_sse_stream


async def test_parse_sse_frames_preserves_events_multiline_data_and_done() -> None:
    response = httpx.Response(
        200,
        content=(
            b"event: snapshot\r\n"
            b'data: {"a": 1}\r\n'
            b'data: {"b": 2}\r\n'
            b"\r\n"
            b"event: done\n"
            b"data: [DONE]\n\n"
        ),
    )

    frames = [frame async for frame in parse_sse_frames(response)]

    assert len(frames) == 1
    assert frames[0].event == "snapshot"
    assert frames[0].data == '{"a": 1}\n{"b": 2}'


async def test_parse_sse_stream_ignores_invalid_json_frames() -> None:
    response = httpx.Response(
        200,
        content=b'data: not-json\n\ndata: {"step":"done","status":"ok"}\n\n',
    )

    events = [event async for event in parse_sse_stream(response)]

    assert events == [{"step": "done", "status": "ok"}]
