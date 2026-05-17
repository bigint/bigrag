from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpx


class UnsafeOutboundUrlError(ValueError):
    pass


@dataclass(frozen=True)
class PinnedOutbound:
    normalized_url: str
    hostname: str
    pinned_ip: str
    port: int
    scheme: str


def normalize_url_root(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeOutboundUrlError("Outbound URL must use http or https.")
    if not parsed.hostname:
        raise UnsafeOutboundUrlError("Outbound URL must include a hostname.")
    if parsed.username or parsed.password:
        raise UnsafeOutboundUrlError("Outbound URL must not include credentials.")

    hostname = parsed.hostname.lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    default_port = 443 if parsed.scheme == "https" else 80
    port = f":{parsed.port}" if parsed.port and parsed.port != default_port else ""
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), f"{hostname}{port}", path, "", "", ""))


def _is_explicitly_allowed(raw_url: str, allowed_urls: Iterable[str]) -> bool:
    try:
        normalized = normalize_url_root(raw_url)
    except UnsafeOutboundUrlError:
        return False
    for allowed in allowed_urls:
        try:
            if normalized == normalize_url_root(allowed):
                return True
        except UnsafeOutboundUrlError:
            continue
    return False


def _is_blocked_ip(
    ip_str: str,
    *,
    allow_private: bool,
    allow_loopback: bool,
) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    if addr.is_unspecified or addr.is_link_local or addr.is_multicast:
        return True
    if addr.is_loopback:
        return not (allow_loopback or allow_private)
    if addr.is_private:
        return not allow_private
    if addr.is_reserved:
        return True
    return False


def _is_cleartext_allowed_ip(
    ip_str: str,
    *,
    allow_private: bool,
    allow_loopback: bool,
) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if addr.is_loopback:
        return allow_loopback or allow_private
    if addr.is_private:
        return allow_private
    return False


def _resolve_host_sync(hostname: str, port: int) -> list[str]:
    try:
        addrinfo = socket.getaddrinfo(hostname, port)
    except socket.gaierror as exc:
        raise UnsafeOutboundUrlError("Outbound URL hostname could not be resolved.") from exc
    return [sockaddr[0] for _, _, _, _, sockaddr in addrinfo]


def validate_outbound_url_sync(
    raw_url: str,
    *,
    purpose: str,
    require_https: bool = True,
    allowed_urls: Iterable[str] = (),
    allow_private: bool = False,
    allow_loopback: bool = False,
) -> str:
    normalized = normalize_url_root(raw_url)
    explicitly_allowed = _is_explicitly_allowed(raw_url, allowed_urls)
    effective_allow_private = allow_private or explicitly_allowed
    effective_allow_loopback = allow_loopback or explicitly_allowed

    parsed = urlparse(normalized)
    is_cleartext = parsed.scheme != "https"
    if require_https and is_cleartext and not (effective_allow_private or effective_allow_loopback):
        raise UnsafeOutboundUrlError(f"{purpose} must use HTTPS.")

    hostname = parsed.hostname
    if hostname is None:
        raise UnsafeOutboundUrlError(f"{purpose} must include a hostname.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = _resolve_host_sync(hostname, port)
    for address in addresses:
        if _is_blocked_ip(
            address,
            allow_private=effective_allow_private,
            allow_loopback=effective_allow_loopback,
        ):
            raise UnsafeOutboundUrlError(
                f"{purpose} must not target private, loopback, link-local, or reserved networks."
            )
        if (
            require_https
            and is_cleartext
            and not _is_cleartext_allowed_ip(
                address,
                allow_private=effective_allow_private,
                allow_loopback=effective_allow_loopback,
            )
        ):
            raise UnsafeOutboundUrlError(f"{purpose} must use HTTPS for public endpoints.")
    return normalized


async def validate_outbound_url(
    raw_url: str,
    *,
    purpose: str,
    require_https: bool = True,
    allowed_urls: Iterable[str] = (),
    allow_private: bool = False,
    allow_loopback: bool = False,
) -> str:
    return await asyncio.to_thread(
        validate_outbound_url_sync,
        raw_url,
        purpose=purpose,
        require_https=require_https,
        allowed_urls=tuple(allowed_urls),
        allow_private=allow_private,
        allow_loopback=allow_loopback,
    )


def validate_embedding_base_url_sync(base_url: str | None) -> str | None:
    if not base_url:
        return None
    from bigrag.services.runtime_settings import sync_value

    return validate_outbound_url_sync(
        base_url,
        purpose="Embedding base URL",
        allowed_urls=sync_value("allowed_embedding_base_urls"),
        allow_private=sync_value("allow_private_embedding_base_urls"),
    )


def validate_chat_base_url_sync(base_url: str | None) -> str | None:
    if not base_url:
        return None
    from bigrag.services.runtime_settings import sync_value

    return validate_outbound_url_sync(
        base_url,
        purpose="Chat provider base URL",
        allowed_urls=sync_value("allowed_chat_base_urls"),
        allow_private=sync_value("allow_private_chat_base_urls"),
    )


async def validate_embedding_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["allowed_embedding_base_urls", "allow_private_embedding_base_urls"])

    return await validate_outbound_url(
        base_url,
        purpose="Embedding base URL",
        allowed_urls=runtime["allowed_embedding_base_urls"],
        allow_private=runtime["allow_private_embedding_base_urls"],
    )


async def validate_chat_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["allowed_chat_base_urls", "allow_private_chat_base_urls"])

    return await validate_outbound_url(
        base_url,
        purpose="Chat provider base URL",
        allowed_urls=runtime["allowed_chat_base_urls"],
        allow_private=runtime["allow_private_chat_base_urls"],
    )


async def validate_webhook_url(url: str) -> str:
    from bigrag.services.runtime_settings import get_value

    allow_local = await get_value("allow_local_webhooks")
    return await validate_outbound_url(
        url,
        purpose="Webhook URL",
        allow_loopback=allow_local,
        allow_private=allow_local,
    )


def resolve_and_pin_sync(
    raw_url: str,
    *,
    purpose: str,
    require_https: bool = True,
    allowed_urls: Iterable[str] = (),
    allow_private: bool = False,
    allow_loopback: bool = False,
) -> PinnedOutbound:
    normalized = validate_outbound_url_sync(
        raw_url,
        purpose=purpose,
        require_https=require_https,
        allowed_urls=allowed_urls,
        allow_private=allow_private,
        allow_loopback=allow_loopback,
    )
    parsed = urlparse(normalized)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    explicitly_allowed = _is_explicitly_allowed(raw_url, allowed_urls)
    effective_allow_private = allow_private or explicitly_allowed
    effective_allow_loopback = allow_loopback or explicitly_allowed
    pinned_ip: str | None = None
    for address in _resolve_host_sync(hostname, port):
        if not _is_blocked_ip(
            address,
            allow_private=effective_allow_private,
            allow_loopback=effective_allow_loopback,
        ):
            pinned_ip = address
            break
    if pinned_ip is None:
        raise UnsafeOutboundUrlError(
            f"{purpose} resolved only to private, loopback, link-local, or reserved addresses."
        )
    return PinnedOutbound(
        normalized_url=normalized,
        hostname=hostname,
        pinned_ip=pinned_ip,
        port=port,
        scheme=parsed.scheme,
    )


async def resolve_and_pin(
    raw_url: str,
    *,
    purpose: str,
    require_https: bool = True,
    allowed_urls: Iterable[str] = (),
    allow_private: bool = False,
    allow_loopback: bool = False,
) -> PinnedOutbound:
    return await asyncio.to_thread(
        resolve_and_pin_sync,
        raw_url,
        purpose=purpose,
        require_https=require_https,
        allowed_urls=tuple(allowed_urls),
        allow_private=allow_private,
        allow_loopback=allow_loopback,
    )


async def pin_chat_base_url(base_url: str) -> PinnedOutbound:
    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["allowed_chat_base_urls", "allow_private_chat_base_urls"])
    return await resolve_and_pin(
        base_url,
        purpose="Chat provider base URL",
        allowed_urls=runtime["allowed_chat_base_urls"],
        allow_private=runtime["allow_private_chat_base_urls"],
    )


async def pin_embedding_base_url(base_url: str) -> PinnedOutbound:
    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["allowed_embedding_base_urls", "allow_private_embedding_base_urls"])
    return await resolve_and_pin(
        base_url,
        purpose="Embedding base URL",
        allowed_urls=runtime["allowed_embedding_base_urls"],
        allow_private=runtime["allow_private_embedding_base_urls"],
    )


async def pin_webhook_url(url: str) -> PinnedOutbound:
    from bigrag.services.runtime_settings import get_value

    allow_local = await get_value("allow_local_webhooks")
    return await resolve_and_pin(
        url,
        purpose="Webhook URL",
        allow_loopback=allow_local,
        allow_private=allow_local,
    )


class _IPPinnedTransport(httpx.AsyncHTTPTransport):
    def __init__(self, hostname: str, pinned_ip: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hostname = hostname.lower()
        self._pinned_ip = pinned_ip

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request_host = (request.url.host or "").lower()
        if request_host != self._hostname and request_host != self._pinned_ip.lower():
            raise httpx.ConnectError(
                f"refused to connect to {request_host}: pinned to {self._hostname}"
            )
        new_url = request.url.copy_with(host=self._pinned_ip)
        new_headers = httpx.Headers(request.headers)
        if "host" not in {k.lower() for k in new_headers}:
            host_value = self._hostname
            if request.url.port:
                host_value = f"{self._hostname}:{request.url.port}"
            new_headers["Host"] = host_value
        extensions = {
            **(request.extensions or {}),
            "sni_hostname": self._hostname,
        }
        new_request = httpx.Request(
            method=request.method,
            url=new_url,
            headers=new_headers,
            stream=request.stream,
            extensions=extensions,
        )
        return await super().handle_async_request(new_request)


def pinned_async_client(
    pinned: PinnedOutbound,
    *,
    timeout: float | None = None,
    follow_redirects: bool = False,
    http2: bool = False,
    verify: bool = True,
) -> httpx.AsyncClient:
    transport = _IPPinnedTransport(
        hostname=pinned.hostname,
        pinned_ip=pinned.pinned_ip,
        verify=verify,
        http2=http2,
    )
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
