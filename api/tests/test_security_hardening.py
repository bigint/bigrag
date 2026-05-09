from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bigrag.config import Settings
from bigrag.exceptions import RateLimitError
from bigrag.routers.connectors import _redirect_uri
from bigrag.services import runtime_settings
from bigrag.services.event_tokens import create_event_token, validate_event_token
from bigrag.services.upload_rate_limit import consume_upload_budget, principal_upload_bucket
from bigrag.services.url_security import UnsafeOutboundUrlError, validate_outbound_url_sync
from bigrag.startup_guard import check_production_safety


def test_prod_guard_rejects_public_bind_without_confirmation() -> None:
    settings = Settings(
        env="prod",
        database_url="postgres://bigrag:secret@localhost:5432/bigrag",
        master_key="present",
        session_cookie_secure=True,
        host="0.0.0.0",
    )

    with pytest.raises(SystemExit):
        check_production_safety(settings)


def test_prod_guard_rejects_cookie_domain_without_trusted_proxy() -> None:
    settings = Settings(
        env="prod",
        database_url="postgres://bigrag:secret@localhost:5432/bigrag",
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
        database_url="postgres://bigrag:secret@localhost:5432/bigrag",
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
    monkeypatch.setattr("bigrag.services.event_tokens.get_redis", lambda: redis)

    token = asyncio.run(create_event_token({"id": "user"}, "docs"))

    assert asyncio.run(validate_event_token(token, "docs")) is True
    assert asyncio.run(validate_event_token(token, "other")) is False


def test_upload_rate_limit_uses_api_key_bucket_and_rejects_overage(monkeypatch) -> None:
    class Redis:
        def __init__(self) -> None:
            self.values = {}

        async def incrby(self, key, amount):
            self.values[key] = self.values.get(key, 0) + amount
            return self.values[key]

        async def expire(self, key, ttl):
            self.expires = (key, ttl)

        async def ttl(self, key):
            return 120

    async def fake_get_values(keys):
        return {
            "upload_rate_limit_files_per_hour": 1,
            "upload_rate_limit_mb_per_hour": 1,
        }

    redis = Redis()
    user = {"id": "user-1", "api_key_id": "key-1"}
    monkeypatch.setattr("bigrag.services.upload_rate_limit.get_redis", lambda: redis)
    monkeypatch.setattr("bigrag.services.upload_rate_limit.get_values", fake_get_values)

    assert principal_upload_bucket(user) == "api_key:key-1"
    asyncio.run(consume_upload_budget(user, files=1, bytes_=0))
    with pytest.raises(RateLimitError) as exc:
        asyncio.run(consume_upload_budget(user, files=1, bytes_=0))

    assert exc.value.retry_after == 120
