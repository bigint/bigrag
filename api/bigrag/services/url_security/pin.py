from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from bigrag.services.url_security.validate import (
    UnsafeOutboundUrlError,
    is_blocked_ip,
    is_explicitly_allowed,
    validate_outbound_url_with_addrs_sync,
)


@dataclass(frozen=True)
class PinnedOutbound:
    normalized_url: str
    hostname: str
    pinned_ip: str
    port: int
    scheme: str


def resolve_and_pin_sync(
    raw_url: str,
    *,
    purpose: str,
    require_https: bool = True,
    allowed_urls: Iterable[str] = (),
    allow_private: bool = False,
    allow_loopback: bool = False,
) -> PinnedOutbound:
    normalized, addresses = validate_outbound_url_with_addrs_sync(
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
    explicitly_allowed = is_explicitly_allowed(raw_url, allowed_urls)
    effective_allow_private = allow_private or explicitly_allowed
    effective_allow_loopback = allow_loopback or explicitly_allowed
    pinned_ip: str | None = None
    for address in addresses:
        if not is_blocked_ip(
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
