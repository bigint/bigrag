from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from rag_computer.config import Settings
from rag_computer.routers.connectors import _redirect_uri
from rag_computer.services import runtime_settings, url_security
from rag_computer.services.event_tokens import create_event_token, validate_event_token
from rag_computer.services.url_security import UnsafeOutboundUrlError, validate_outbound_url_sync
from rag_computer.startup_guard import check_production_safety


def test_prod_guard_rejects_public_bind_without_confirmation() -> None:
    settings = Settings(
        env="prod",
        database_url="postgres://rag_computer:secret@localhost:5432/rag_computer",
        master_key="present",
        session_cookie_secure=True,
        host="0.0.0.0",
    )

    with pytest.raises(SystemExit):
        check_production_safety(settings)


def test_prod_guard_rejects_cookie_domain_without_trusted_proxy() -> None:
    settings = Settings(
        env="prod",
        database_url="postgres://rag_computer:secret@localhost:5432/rag_computer",
        master_key="present",
        session_cookie_secure=True,
        host="127.0.0.1",
        session_cookie_domain=".example.com",
        trusted_proxies=[],
    )

    with pytest.raises(SystemExit):
        check_production_safety(settings)


def test_prod_guard_allows_hardened_prod_config() -> None:
    settings = Settings(
        env="prod",
        database_url="postgres://rag_computer:secret@localhost:5432/rag_computer",
        master_key="present",
        session_cookie_secure=True,
        host="0.0.0.0",
        allow_public_bind_in_prod=True,
        session_cookie_domain=".example.com",
        trusted_proxies=["10.0.0.0/8"],
    )

    check_production_safety(settings)


def test_connector_redirect_ignores_untrusted_forwarded_headers(monkeypatch) -> None:
    monkeypatch.setattr(runtime_settings, "sync_value", lambda key: [])
    request = SimpleNamespace(
        headers={"x-forwarded-host": "evil.example", "x-forwarded-proto": "https"},
        client=("203.0.113.10", 12345),
        url_for=lambda name, provider_slug: (
            f"http://api.internal:4000/v1/connectors/{provider_slug}/oauth/callback"
        ),
    )

    assert (
        _redirect_uri(request, SimpleNamespace(slug="google-drive"))
        == "http://api.internal:4000/v1/connectors/google-drive/oauth/callback"
    )


def test_connector_redirect_trusts_forwarded_headers_from_trusted_proxy(monkeypatch) -> None:
    monkeypatch.setattr(runtime_settings, "sync_value", lambda key: ["10.0.0.0/8"])
    request = SimpleNamespace(
        headers={
            "x-forwarded-host": "admin.example.com",
            "x-forwarded-proto": "https",
            "x-forwarded-prefix": "/api",
        },
        client=("10.1.2.3", 12345),
        url=SimpleNamespace(scheme="http"),
    )

    assert (
        _redirect_uri(request, SimpleNamespace(slug="google-drive"))
        == "https://admin.example.com/api/v1/connectors/google-drive/oauth/callback"
    )


def test_outbound_url_rejects_private_resolution(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.5", 443))],
    )

    with pytest.raises(UnsafeOutboundUrlError):
        validate_outbound_url_sync("https://storage.example", purpose="Webhook URL")


def test_outbound_url_normalization_and_parse_rejections() -> None:
    assert url_security.normalize_url_root("HTTPS://Example.COM:443/api///?x=1#frag") == (
        "https://example.com/api"
    )
    assert url_security.normalize_url_root("http://[::1]:8080/root/") == "http://[::1]:8080/root"

    for raw_url, message in [
        ("ftp://example.com", "must use http or https"),
        ("https:///missing", "must include a hostname"),
        ("https://user:pass@example.com", "must not include credentials"),
    ]:
        with pytest.raises(UnsafeOutboundUrlError, match=message):
            url_security.normalize_url_root(raw_url)


def test_outbound_url_allows_explicit_match_without_resolution(monkeypatch) -> None:
    def fail_resolution(*_args, **_kwargs):
        raise AssertionError("explicit allowlist should skip DNS")

    monkeypatch.setattr("socket.getaddrinfo", fail_resolution)

    assert (
        validate_outbound_url_sync(
            "http://allowed.internal/root/",
            purpose="Embedding base URL",
            allowed_urls=["http://allowed.internal/root"],
        )
        == "http://allowed.internal/root"
    )


def test_outbound_url_rejects_dns_and_public_cleartext(monkeypatch) -> None:
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 80))],
    )

    with pytest.raises(UnsafeOutboundUrlError, match="must use HTTPS"):
        validate_outbound_url_sync("http://example.com", purpose="Webhook URL")

    with pytest.raises(UnsafeOutboundUrlError, match="must use HTTPS for public endpoints"):
        validate_outbound_url_sync(
            "http://example.com",
            purpose="Webhook URL",
            allow_private=True,
        )

    assert (
        validate_outbound_url_sync("https://example.com", purpose="Webhook URL")
        == "https://example.com"
    )

    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("10.0.0.5", 80))],
    )

    assert (
        validate_outbound_url_sync(
            "http://internal.example",
            purpose="Embedding base URL",
            allow_private=True,
        )
        == "http://internal.example"
    )


def test_outbound_url_rejects_unresolvable_and_special_ips(monkeypatch) -> None:
    import socket

    def unresolved(*_args, **_kwargs):
        raise socket.gaierror("missing")

    monkeypatch.setattr("socket.getaddrinfo", unresolved)

    with pytest.raises(UnsafeOutboundUrlError, match="could not be resolved"):
        validate_outbound_url_sync("https://missing.example", purpose="Webhook URL")

    assert url_security._is_blocked_ip("not-an-ip", allow_private=False, allow_loopback=False)
    assert url_security._is_blocked_ip("0.0.0.0", allow_private=True, allow_loopback=True)
    assert url_security._is_blocked_ip("127.0.0.1", allow_private=False, allow_loopback=False)
    assert not url_security._is_blocked_ip("127.0.0.1", allow_private=False, allow_loopback=True)
    assert url_security._is_cleartext_allowed_ip(
        "10.0.0.5", allow_private=True, allow_loopback=False
    )
    assert not url_security._is_cleartext_allowed_ip(
        "93.184.216.34", allow_private=True, allow_loopback=True
    )
    assert not url_security._is_cleartext_allowed_ip(
        "not-an-ip", allow_private=True, allow_loopback=True
    )


def test_outbound_url_runtime_wrappers(monkeypatch) -> None:
    async def get_values(keys):
        if keys == ["allowed_embedding_base_urls", "allow_private_embedding_base_urls"]:
            return {
                "allowed_embedding_base_urls": ["https://embed.example"],
                "allow_private_embedding_base_urls": False,
            }
        return {
            "allowed_chat_base_urls": ["https://chat.example"],
            "allow_private_chat_base_urls": False,
        }

    async def get_value(_key):
        return True

    monkeypatch.setattr("rag_computer.services.runtime_settings.get_values", get_values)
    monkeypatch.setattr("rag_computer.services.runtime_settings.get_value", get_value)

    assert asyncio.run(url_security.validate_embedding_base_url(None)) is None
    assert asyncio.run(url_security.validate_chat_base_url(None)) is None
    assert (
        asyncio.run(url_security.validate_embedding_base_url("https://embed.example/"))
        == "https://embed.example"
    )
    assert (
        asyncio.run(url_security.validate_chat_base_url("https://chat.example/"))
        == "https://chat.example"
    )

    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 80))],
    )

    assert asyncio.run(url_security.validate_webhook_url("http://localhost:4000/hook")) == (
        "http://localhost:4000/hook"
    )


def test_event_tokens_are_collection_bound(monkeypatch) -> None:
    class Redis:
        def __init__(self) -> None:
            self.values = {}

        async def set(self, key, value, ex):
            self.values[key] = value

        async def get(self, key):
            return self.values.get(key)

        async def expire(self, key, ex):
            self.expires = (key, ex)

    redis = Redis()
    monkeypatch.setattr("rag_computer.services.event_tokens.get_redis", lambda: redis)

    token = asyncio.run(create_event_token({"id": "user"}, "docs"))

    assert asyncio.run(validate_event_token(token, "docs")) is True
    assert asyncio.run(validate_event_token(token, "other")) is False
