from __future__ import annotations

import asyncio

import httpx
import pytest

from bigrag import BigRAG
from bigrag._core import USER_AGENT
from bigrag._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)


def run(coro):
    return asyncio.run(coro)


def json_response(
    status_code: int, body: dict, request: httpx.Request
) -> httpx.Response:
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
        (500, InternalServerError),
    ]

    for status_code, error_type in cases:

        def handler(request: httpx.Request) -> httpx.Response:
            return json_response(
                status_code, {"detail": f"status {status_code}"}, request
            )

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
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(timeout_handler)
            ),
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
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(connection_handler)
            ),
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


def test_retries_rate_limit_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return json_response(429, {"detail": "slow down"}, request)
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


def test_request_with_json_sets_content_type() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(200, {"id": "created"}, request)

    async def scenario() -> dict:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return await client._request(
                "POST", "/v1/collections", json={"name": "docs"}
            )
        finally:
            await client.aclose()

    assert run(scenario()) == {"id": "created"}
    assert seen[0].headers["content-type"] == "application/json"
    assert seen[0].content == b'{"name":"docs"}'


def test_retries_timeout_and_connection_errors_before_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    timeout_calls = 0

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        raise httpx.TimeoutException("deadline", request=request)

    async def timeout_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            max_retries=1,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(timeout_handler)
            ),
        )
        try:
            await client.health()
        finally:
            await client.aclose()

    with pytest.raises(APITimeoutError):
        run(timeout_scenario())
    assert timeout_calls == 2

    connection_calls = 0

    def connection_handler(request: httpx.Request) -> httpx.Response:
        nonlocal connection_calls
        connection_calls += 1
        raise httpx.ConnectError("socket closed", request=request)

    async def connection_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            max_retries=1,
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(connection_handler)
            ),
        )
        try:
            await client.health()
        finally:
            await client.aclose()

    with pytest.raises(APIConnectionError):
        run(connection_scenario())
    assert connection_calls == 2


def test_execute_with_retry_handles_no_attempt_configuration() -> None:
    async def scenario() -> None:
        client = BigRAG(base_url="http://api.local", max_retries=-1)
        try:
            await client._execute_with_retry(lambda: None)
        finally:
            await client.aclose()

    with pytest.raises(APIConnectionError, match="Request failed"):
        run(scenario())


def test_no_content_and_empty_responses_return_ok_status() -> None:
    responses = [httpx.Response(204), httpx.Response(200, content=b"")]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    async def scenario() -> list[dict]:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return [await client.health(), await client.readiness()]
        finally:
            await client.aclose()

    assert run(scenario()) == [{"status": "ok"}, {"status": "ok"}]


def test_form_errors_and_non_json_error_fallbacks_map_to_api_errors() -> None:
    def form_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "bad form", "code": "BAD_FORM"}},
            request=request,
        )

    async def form_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(form_handler)),
        )
        try:
            await client._request_form("/upload", files={"file": ("a.txt", b"a")})
        finally:
            await client.aclose()

    with pytest.raises(APIError) as form_error:
        run(form_scenario())
    assert form_error.value.status == 400
    assert form_error.value.code == "BAD_FORM"
    assert str(form_error.value) == "bad form"

    def text_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, text="no json", request=request)

    async def text_scenario() -> None:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(text_handler)),
        )
        try:
            await client.health()
        finally:
            await client.aclose()

    with pytest.raises(APIError) as text_error:
        run(text_scenario())
    assert text_error.value.status == 418
    assert str(text_error.value) == "I'm a teapot"


def test_owned_client_context_manager_closes_client() -> None:
    async def scenario() -> bool:
        async with BigRAG(base_url="http://api.local") as client:
            owned = client._client
        return owned.is_closed

    assert run(scenario()) is True
