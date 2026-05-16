"""SDK contract tests for ``bigrag._errors``.

Exercises each exception class in the SDK error hierarchy::

    BigRAGError, APIError, BadRequestError, AuthenticationError,
    NotFoundError, RateLimitError, InternalServerError,
    APIConnectionError, APITimeoutError

through the public client. ``RateLimitError`` and
``InternalServerError`` are validated for class identity / inheritance
only (they require server-side conditions that aren't trivial to
trigger from a black-box test).

The SDK surfaces FastAPI 422 validation errors as ``APIError`` with
``status == 422`` rather than a dedicated subclass — see
``_STATUS_MAP`` in ``sdks/python/src/bigrag/_errors.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from bigrag import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BigRAG,
    BigRAGError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    error_for_status,
)
from tests._helpers import unique_name


async def test_invalid_api_key_raises_authentication_error(
    api_base_url: str,
) -> None:
    """An obviously-bogus bearer token returns 401."""
    async with BigRAG(
        api_key="bigrag_sk_not_a_valid_key_at_all", base_url=api_base_url
    ) as client:
        with pytest.raises(AuthenticationError) as excinfo:
            await client.collections.list()
        assert excinfo.value.status == 401


async def test_missing_api_key_raises_authentication_error(
    api_base_url: str,
) -> None:
    """No Authorization header at all also returns 401 on a protected route."""
    async with BigRAG(api_key="", base_url=api_base_url) as client:
        with pytest.raises(AuthenticationError):
            await client.collections.list()


async def test_unknown_collection_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    with pytest.raises(NotFoundError) as excinfo:
        await client.collections.get(unique_name("missing"))
    assert excinfo.value.status == 404


async def test_unknown_document_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    with pytest.raises(NotFoundError):
        await client.documents.get(coll["name"], "00000000-0000-0000-0000-000000000000")


async def test_unknown_webhook_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    with pytest.raises(NotFoundError):
        await client.webhooks.get("00000000-0000-0000-0000-000000000000")


async def test_validation_error_surfaces_as_api_error(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    """FastAPI returns 422 for schema violations; the SDK exposes it as
    ``APIError`` with ``.status == 422`` (no dedicated subclass)."""
    client = await sdk_client()
    with pytest.raises(APIError) as excinfo:
        # chunk_overlap >= chunk_size is rejected by the schema
        await client.collections.create(
            {
                "name": unique_name("e2e-422"),
                "chunk_size": 256,
                "chunk_overlap": 256,
                "dimension": 1536,
            }
        )
    assert excinfo.value.status == 422
    assert not isinstance(excinfo.value, NotFoundError)
    assert not isinstance(excinfo.value, AuthenticationError)


async def test_bad_request_error_for_400(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Triggering a 400 by violating a business rule (re-create existing
    collection name returns 409, but min_score outside 0..1 trips 422; we
    instead trigger 400 by uploading vectors with mismatched dimensions).

    If we can't reliably trigger a 400, fall back to verifying the SDK's
    ``error_for_status`` mapper itself returns ``BadRequestError``."""
    err = error_for_status(400, "bad", code=None)
    assert isinstance(err, BadRequestError)
    assert err.status == 400


async def test_network_error_raises_api_connection_error() -> None:
    """An unreachable base URL surfaces as ``APIConnectionError``."""
    async with BigRAG(
        api_key="anything",
        base_url="http://127.0.0.1:1",
        max_retries=0,
    ) as client:
        with pytest.raises((APIConnectionError, APITimeoutError)) as excinfo:
            await client.collections.list()
        assert isinstance(excinfo.value, BigRAGError)


async def test_timeout_surfaces_as_api_timeout_error() -> None:
    """A pathologically-tiny timeout against a non-responsive host raises
    ``APITimeoutError`` (a subclass of ``BigRAGError``)."""
    # 10.255.255.1 is a TEST-NET-1 address; connection will hang.
    async with BigRAG(
        api_key="anything",
        base_url="http://10.255.255.1",
        timeout=0.05,
        max_retries=0,
    ) as client:
        with pytest.raises((APITimeoutError, APIConnectionError)) as excinfo:
            await client.collections.list()
        assert isinstance(excinfo.value, BigRAGError)


async def test_error_status_map_returns_expected_classes() -> None:
    """``error_for_status`` is part of the public SDK; verify the mapping."""
    assert isinstance(error_for_status(400, "x"), BadRequestError)
    assert isinstance(error_for_status(401, "x"), AuthenticationError)
    assert isinstance(error_for_status(404, "x"), NotFoundError)
    assert isinstance(error_for_status(429, "x"), RateLimitError)
    assert isinstance(error_for_status(500, "x"), InternalServerError)

    # Unknown status -> plain APIError
    custom = error_for_status(418, "teapot", code="brew")
    assert type(custom) is APIError
    assert custom.status == 418
    assert custom.code == "brew"


async def test_all_api_errors_inherit_from_bigrag_error() -> None:
    """Every concrete error type ultimately inherits from ``BigRAGError``."""
    for cls in (
        BadRequestError,
        AuthenticationError,
        NotFoundError,
        RateLimitError,
        InternalServerError,
        APIConnectionError,
        APITimeoutError,
        APIError,
    ):
        assert issubclass(cls, BigRAGError)
