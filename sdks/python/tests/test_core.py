from __future__ import annotations

import asyncio

import httpx
import pytest

from bigrag import BigRAG
from bigrag._core import USER_AGENT
from bigrag._errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)


def run(coro):
    return asyncio.run(coro)


def json_response(status_code: int, body: dict, request: httpx.Request) -> httpx.Response:
    return httpx.Response(status_code, json=body, request=request)


def test_request_sends_auth_user_agent_query_and_parses_json() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(200, {"status": "ok"}, request)

    async def scenario() -> dict:
        client = BigRAG(
            api_key="bigrag_sk_test",
            base_url="http://api.local/",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return await client.get_usage(window_days=7)
        finally:
            await client.aclose()

    assert run(scenario()) == {"status": "ok"}
    assert str(seen[0].url) == "http://api.local/v1/usage?window_days=7"
    assert seen[0].headers["authorization"] == "Bearer bigrag_sk_test"
    assert seen[0].headers["user-agent"] == USER_AGENT


def test_error_responses_map_to_typed_errors() -> None:
    cases = [
        (401, AuthenticationError),
        (404, NotFoundError),
        (429, RateLimitError),
    ]

    for status_code, error_type in cases:

        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(status_code, {"detail": f"status {status_code}"}, request)

        async def scenario() -> None:
            client = BigRAG(
                base_url="http://api.local",
                max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            )
            try:
                await client.health()
            finally:
                await client.aclose()

        with pytest.raises(error_type):
            run(scenario())


def test_timeout_and_connection_errors_map_to_typed_errors() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("deadline", request=request)

    async def timeout_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)),
        )
        try:
            await client.health()
        finally:
            await client.aclose()

    with pytest.raises(APITimeoutError):
        run(timeout_scenario())

    def connection_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("socket closed", request=request)

    async def connection_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(connection_handler)),
        )
        try:
            await client.health()
        finally:
            await client.aclose()

    with pytest.raises(APIConnectionError):
        run(connection_scenario())


def test_retries_transient_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return json_response(503, {"detail": "temporary"}, request)
        return json_response(200, {"status": "ok"}, request)

    async def scenario() -> dict:
        client = BigRAG(
            base_url="http://api.local",
            max_retries=1,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return await client.health()
        finally:
            await client.aclose()

    assert run(scenario()) == {"status": "ok"}
    assert calls == 2
