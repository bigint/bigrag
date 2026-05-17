from __future__ import annotations

import asyncio
import secrets

import httpx

_RNG = secrets.SystemRandom()
_SEMAPHORES: dict[str, asyncio.Semaphore] = {}


def get_semaphore(webhook_id: str) -> asyncio.Semaphore:
    if webhook_id not in _SEMAPHORES:
        _SEMAPHORES[webhook_id] = asyncio.Semaphore(5)
    return _SEMAPHORES[webhook_id]


def retry_delays() -> list[int]:
    from bigrag.services.runtime_settings import sync_value

    return sync_value("webhook_retry_delays")


def delivery_timeout() -> int:
    from bigrag.services.runtime_settings import sync_value

    return sync_value("webhook_delivery_timeout")


def jittered_delay(base_delay: int, jitter_factor: float = 0.25) -> float:
    jitter = base_delay * jitter_factor
    return base_delay + _RNG.uniform(-jitter, jitter)


async def post_pinned(
    url: str,
    payload: str,
    headers: dict[str, str],
) -> httpx.Response:
    from bigrag.services.runtime_settings import get_value
    from bigrag.services.url_security import pinned_async_client, resolve_and_pin

    allow_local = await get_value("allow_local_webhooks")
    timeout = delivery_timeout()
    pinned = await resolve_and_pin(
        url,
        purpose="Webhook URL",
        allow_loopback=allow_local,
        allow_private=allow_local,
    )
    async with pinned_async_client(
        pinned,
        timeout=timeout,
        follow_redirects=False,
    ) as client:
        return await client.post(url, content=payload, headers=headers)
