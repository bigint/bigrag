from __future__ import annotations

from collections.abc import Iterator

import pytest

from bigrag.config import settings
from bigrag.services.client_ip import _trusted_networks, client_ip_from_scope


@pytest.fixture(autouse=True)
def reset_trusted_proxies() -> Iterator[None]:
    original = list(settings.trusted_proxies)
    _trusted_networks.cache_clear()
    yield
    settings.trusted_proxies = original
    _trusted_networks.cache_clear()


def _scope(client_ip: str, forwarded_for: str | None = None) -> dict:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("latin-1")))
    return {"client": (client_ip, 12345), "headers": headers}


def test_untrusted_proxy_ignores_forwarded_for() -> None:
    settings.trusted_proxies = []
    _trusted_networks.cache_clear()

    assert client_ip_from_scope(_scope("10.0.0.10", "203.0.113.5")) == "10.0.0.10"


def test_trusted_proxy_uses_nearest_untrusted_forwarded_ip() -> None:
    settings.trusted_proxies = ["10.0.0.0/8", "192.0.2.0/24"]
    _trusted_networks.cache_clear()

    scope = _scope("10.0.0.10", "198.51.100.1, 192.0.2.2")

    assert client_ip_from_scope(scope) == "198.51.100.1"
