"""Local fixtures for the opt-in real-OpenAI smoke pass.

The whole package is skipped unless ``BIGRAG_E2E_REAL_OPENAI=1`` is set in
the environment. When enabled, ``real_openai_settings`` flips the running
bigRAG instance's runtime settings to point embedding + chat at the real
OpenAI API for the duration of the session, then restores the e2e
fake-openai defaults on teardown.

Budget: <= 5 OpenAI calls per run. Tests use the cheapest models
(``text-embedding-3-small``, ``gpt-4o-mini``) with tiny inputs.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from tests._helpers import assert_envelope

pytestmark = pytest.mark.skipif(
    not os.getenv("BIGRAG_E2E_REAL_OPENAI"),
    reason="real OpenAI smoke disabled by default (set BIGRAG_E2E_REAL_OPENAI=1 to enable)",
)


REAL_OPENAI_BASE_URL = "https://api.openai.com/v1"
REAL_EMBEDDING_MODEL = "text-embedding-3-small"
REAL_EMBEDDING_DIMENSION = 1536
REAL_CHAT_MODEL = "gpt-4o-mini"

FAKE_OPENAI_BASE_URL = "http://fake-openai:9001/v1"
FAKE_API_KEY = "e2e-fake-key"


_OVERRIDE_KEYS = (
    "embedding_provider",
    "embedding_model",
    "embedding_dimension",
    "embedding_base_url",
    "embedding_api_key",
    "chat_provider",
    "chat_model",
    "chat_base_url",
    "chat_api_key",
)


@pytest_asyncio.fixture(scope="session")
async def real_openai_settings(
    admin_setup: dict[str, str],
) -> AsyncIterator[dict[str, object]]:
    """Override embedding + chat settings to point at real OpenAI.

    Skips if ``OPENAI_API_KEY`` is missing. Restores the fake-openai
    defaults (matching ``docker-compose.e2e.yml``) on teardown rather
    than trying to round-trip secret values that the API will not echo.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is not set; real-OpenAI smoke cannot run")

    from conftest import API_BASE, DEFAULT_TIMEOUT, _OriginAwareClient

    async with _OriginAwareClient(
        base_url=API_BASE,
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        origin=API_BASE,
    ) as client:
        login = await client.post(
            "/v1/auth/login",
            json={
                "email": admin_setup["email"],
                "password": admin_setup["password"],
            },
        )
        if login.status_code != 200:
            raise RuntimeError(
                f"admin login failed for real-openai setup: {login.status_code} {login.text}"
            )

        real_values = {
            "embedding_provider": "openai",
            "embedding_model": REAL_EMBEDDING_MODEL,
            "embedding_dimension": REAL_EMBEDDING_DIMENSION,
            "embedding_base_url": REAL_OPENAI_BASE_URL,
            "embedding_api_key": api_key,
            "chat_provider": "openai",
            "chat_model": REAL_CHAT_MODEL,
            "chat_base_url": REAL_OPENAI_BASE_URL,
            "chat_api_key": api_key,
        }
        resp = await client.put("/v1/admin/settings", json={"values": real_values})
        assert_envelope(resp, 200)

        try:
            yield {
                "embedding_model": REAL_EMBEDDING_MODEL,
                "embedding_dimension": REAL_EMBEDDING_DIMENSION,
                "chat_model": REAL_CHAT_MODEL,
            }
        finally:
            restore_values = {
                "embedding_provider": "openai_compatible",
                "embedding_model": REAL_EMBEDDING_MODEL,
                "embedding_dimension": REAL_EMBEDDING_DIMENSION,
                "embedding_base_url": FAKE_OPENAI_BASE_URL,
                "embedding_api_key": FAKE_API_KEY,
                "chat_provider": "openai_compatible",
                "chat_model": REAL_CHAT_MODEL,
                "chat_base_url": FAKE_OPENAI_BASE_URL,
                "chat_api_key": FAKE_API_KEY,
            }
            try:
                await client.put(
                    "/v1/admin/settings",
                    json={"values": restore_values},
                )
            except httpx.HTTPError:
                pass
