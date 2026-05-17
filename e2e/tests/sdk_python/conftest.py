"""Fixtures specific to the ``sdks/python`` Python SDK suite.

Exposes a ``sdk_client`` factory that returns an async-context-managed
:class:`bigrag.BigRAG` instance. The factory tracks every client it mints
and closes them on teardown so individual tests don't have to.

Most SDK calls are exercised against the API key principal (the SDK's
default auth method). Tests that need a session-authenticated client
build one inline using ``BigRAG(http_client=...)`` with a pre-configured
``httpx.AsyncClient`` carrying the login cookie and an ``Origin`` header.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest_asyncio

from bigrag import BigRAG

SdkClientFactory = Callable[..., Awaitable[BigRAG]]


@pytest_asyncio.fixture
async def sdk_client(
    api_base_url: str,
    api_key: Callable[..., Awaitable[dict[str, Any]]],
) -> AsyncIterator[SdkClientFactory]:
    """Factory that mints a :class:`bigrag.BigRAG` bound to an API key.

    Each call returns a fresh client. All clients are closed on teardown.

    Usage::

        client = await sdk_client()
        coll = await client.collections.list()

        # custom scopes:
        ro = await sdk_client(scopes=["collection:read"])

        # bring your own key (useful for negative tests):
        bad = await sdk_client(key="bigrag_sk_not_a_real_key")
    """
    created: list[BigRAG] = []

    async def _build(
        *,
        key: str | dict[str, Any] | None = None,
        scopes: list[str] | None = None,
        collection: str | None = None,
        base_url: str | None = None,
    ) -> BigRAG:
        if key is None:
            minted = await api_key(scopes=scopes, collection=collection)
            api_key_value = minted["key"]
        elif isinstance(key, dict):
            api_key_value = key["key"]
        else:
            api_key_value = key
        client = BigRAG(
            api_key=api_key_value,
            base_url=base_url or api_base_url,
        )
        created.append(client)
        return client

    try:
        yield _build
    finally:
        for client in created:
            try:
                await client.aclose()
            except Exception:
                pass


@pytest_asyncio.fixture
async def session_sdk_client(
    admin_setup: dict[str, str],
    api_base_url: str,
) -> AsyncIterator[BigRAG]:
    """Return a :class:`bigrag.BigRAG` authenticated by session cookie.

    bigRAG's CSRF middleware requires an ``Origin`` header on mutating
    requests authenticated by session, so the underlying ``httpx`` client
    sets it as a default header. The session cookie is established by
    calling ``client.auth.login`` before the fixture yields.
    """
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={"Origin": api_base_url},
    )
    client = BigRAG(
        api_key="",
        base_url=api_base_url,
        http_client=http_client,
    )
    await client.auth.login(
        {"email": admin_setup["email"], "password": admin_setup["password"]}
    )
    try:
        yield client
    finally:
        try:
            await client.auth.logout()
        except Exception:
            pass
        await http_client.aclose()
