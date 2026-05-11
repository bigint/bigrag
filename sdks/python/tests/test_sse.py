from __future__ import annotations

import asyncio

import httpx
import pytest

from bigrag import BigRAG
from bigrag._errors import AuthenticationError
from bigrag._sse import parse_sse_stream


def run(coro):
    return asyncio.run(coro)


def stream_response(text: str) -> httpx.Response:
    request = httpx.Request("GET", "http://api.local/events")
    return httpx.Response(200, text=text, request=request)


class AsyncChunks(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk


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


def test_chat_resource_stream_parses_split_frames_and_done() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            stream=AsyncChunks(
                [
                    b'event: delta\ndata: {"delta":"hel',
                    b'lo"}\n\ndata: [DONE]\n\n',
                    b'event: done\ndata: {"ok":true}\n\n',
                ]
            ),
            request=request,
        )

    async def scenario() -> list[dict]:
        client = BigRAG(
            api_key="bigrag_sk_test",
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            events = []
            async for event in client.chat.stream(
                {"message": "hello", "collection": "docs"}
            ):
                events.append(event)
            return events
        finally:
            await client.aclose()

    assert run(scenario()) == [
        {"event": "delta", "data": {"delta": "hello"}},
        {"event": "done", "data": {"ok": True}},
    ]
    assert seen[0].method == "POST"
    assert str(seen[0].url) == "http://api.local/v1/chat"
    assert seen[0].headers["authorization"] == "Bearer bigrag_sk_test"
    assert seen[0].headers["content-type"] == "application/json"
    assert b'"stream":true' in seen[0].content.replace(b" ", b"")


def test_chat_resource_stream_wraps_malformed_json_as_raw() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=AsyncChunks([b"event: delta\ndata: nope\n\n"]),
            request=request,
        )

    async def scenario() -> list[dict]:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            events = []
            async for event in client.chat.stream(
                {"message": "hello", "collection": "docs"}
            ):
                events.append(event)
            return events
        finally:
            await client.aclose()

    assert run(scenario()) == [{"event": "delta", "data": {"raw": "nope"}}]


def test_chat_resource_stream_maps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"detail": "bad key"},
            request=request,
        )

    async def scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            async for _event in client.chat.stream(
                {"message": "hello", "collection": "docs"}
            ):
                pass
        finally:
            await client.aclose()

    with pytest.raises(AuthenticationError, match="bad key"):
        run(scenario())
