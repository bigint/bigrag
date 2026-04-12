"""Unit tests for bigrag.services.credential_check."""

from __future__ import annotations

import httpx
import pytest

from bigrag.services.credential_check import (
    CredentialCheckError,
    verify_provider_credentials,
)


def _mock_client(status_code: int | None = None, exc: Exception | None = None):
    """Returns a factory for httpx.AsyncClient that responds with a canned status or raises."""

    def handler(request: httpx.Request) -> httpx.Response:
        if exc is not None:
            raise exc
        assert status_code is not None
        return httpx.Response(status_code, json={"data": []})

    transport = httpx.MockTransport(handler)
    return transport


async def test_openai_200_returns_none(monkeypatch):
    transport = _mock_client(status_code=200)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    # Should not raise
    await verify_provider_credentials(
        provider="openai", api_key="sk-good", base_url=None
    )


async def test_openai_custom_base_url_200(monkeypatch):
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"data": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    await verify_provider_credentials(
        provider="openai",
        api_key="sk-good",
        base_url="https://ollama.example.com/v1",
    )
    assert seen["url"] == "https://ollama.example.com/v1/models"


async def test_401_raises_invalid_key(monkeypatch):
    transport = _mock_client(status_code=401)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-bad", base_url=None
        )
    assert exc.value.code == "INVALID_KEY"


async def test_403_raises_invalid_key(monkeypatch):
    transport = _mock_client(status_code=403)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-bad", base_url=None
        )
    assert exc.value.code == "INVALID_KEY"


async def test_404_raises_not_found(monkeypatch):
    transport = _mock_client(status_code=404)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai",
            api_key="sk-good",
            base_url="https://self-hosted.example.com/v1",
        )
    assert exc.value.code == "NOT_FOUND"


async def test_503_raises_provider_error(monkeypatch):
    transport = _mock_client(status_code=503)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "PROVIDER_ERROR"
    assert "503" in exc.value.message


async def test_connect_error_raises_unreachable(monkeypatch):
    transport = _mock_client(exc=httpx.ConnectError("refused"))
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "UNREACHABLE"


async def test_timeout_raises_timeout(monkeypatch):
    transport = _mock_client(exc=httpx.TimeoutException("slow"))
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    with pytest.raises(CredentialCheckError) as exc:
        await verify_provider_credentials(
            provider="openai", api_key="sk-good", base_url=None
        )
    assert exc.value.code == "TIMEOUT"


async def test_cohere_hits_cohere_ai(monkeypatch):
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"models": []})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    await verify_provider_credentials(
        provider="cohere", api_key="co-good", base_url=None
    )
    assert seen["url"] == "https://api.cohere.ai/v1/models"
    assert seen["auth"] == "Bearer co-good"


async def test_api_key_not_in_logs(monkeypatch, caplog):
    transport = _mock_client(status_code=401)
    monkeypatch.setattr(
        "bigrag.services.credential_check._build_client",
        lambda timeout: httpx.AsyncClient(transport=transport, timeout=timeout),
    )
    import logging

    caplog.set_level(logging.DEBUG, logger="bigrag.services.credential_check")
    with pytest.raises(CredentialCheckError):
        await verify_provider_credentials(
            provider="openai",
            api_key="sk-SECRET-TOKEN-12345",
            base_url=None,
        )
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "sk-SECRET-TOKEN-12345" not in joined
