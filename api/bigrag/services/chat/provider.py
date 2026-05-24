from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any

from bigrag.exceptions import ServerError, UpstreamError
from bigrag.logging import get_logger
from bigrag.services.url_security import (
    UnsafeOutboundUrlError,
    pin_chat_base_url,
    pinned_async_client,
)

from .formatting import _safe_chat_error
from .types import PreparedChatTurn, ProviderCredential

logger = get_logger("bigrag.chat")

_MODEL_TIMEOUT_SECONDS = 60
_CHAT_CLIENT_TTL_SECONDS = 300
_CHAT_CLIENTS_MAX = 64

_chat_clients: OrderedDict[tuple[str, str], tuple[Any, float]] = OrderedDict()
_chat_clients_lock = asyncio.Lock()


async def close_chat_clients() -> None:
    entries = list(_chat_clients.values())
    _chat_clients.clear()
    for client, _created_at in entries:
        try:
            await client.close()
        except Exception as exc:
            logger.warning("failed to close chat client", error=repr(exc))


async def _complete_model(prepared: PreparedChatTurn) -> str:
    try:
        import openai
    except ImportError as exc:
        raise ServerError(
            "openai package is required for chat",
            public_message="openai package is required for chat",
        ) from exc

    last_error: Exception | None = None
    for credential in prepared.credentials:
        client = await _openai_client(openai, prepared, credential)
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=prepared.model,
                    messages=prepared.model_messages,
                    temperature=prepared.temperature,
                ),
                timeout=_MODEL_TIMEOUT_SECONDS,
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                return ""
            return getattr(choices[0].message, "content", None) or ""
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
            logger.warning(
                "chat provider rejected credential, trying fallback",
                source=credential.source,
                error=_safe_chat_error(exc),
            )
    if last_error is not None:
        raise _provider_error(last_error, prepared.credentials[-1]) from last_error
    return ""


async def _stream_model(prepared: PreparedChatTurn) -> AsyncIterator[str]:
    try:
        import openai
    except ImportError as exc:
        raise ServerError(
            "openai package is required for chat",
            public_message="openai package is required for chat",
        ) from exc

    last_error: Exception | None = None
    for credential in prepared.credentials:
        client = await _openai_client(openai, prepared, credential)
        try:
            stream = await asyncio.wait_for(
                client.chat.completions.create(
                    model=prepared.model,
                    messages=prepared.model_messages,
                    temperature=prepared.temperature,
                    stream=True,
                ),
                timeout=_MODEL_TIMEOUT_SECONDS,
            )
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0].delta, "content", None)
                if delta:
                    yield delta
            return
        except Exception as exc:
            last_error = exc
            if not _should_try_next_credential(exc, prepared, credential):
                raise _provider_error(exc, credential) from exc
            logger.warning(
                "chat provider rejected credential, trying fallback",
                source=credential.source,
                error=_safe_chat_error(exc),
            )
    if last_error is not None:
        raise _provider_error(last_error, prepared.credentials[-1]) from last_error


async def _openai_client(openai_module, prepared: PreparedChatTurn, credential: ProviderCredential):
    base_url = prepared.base_url or "https://api.openai.com/v1"
    cache_key = (
        hashlib.sha256(credential.api_key.encode()).hexdigest(),
        base_url,
    )
    now = time.monotonic()
    entry = _chat_clients.get(cache_key)
    if entry is not None and now - entry[1] < _CHAT_CLIENT_TTL_SECONDS:
        return entry[0]
    async with _chat_clients_lock:
        entry = _chat_clients.get(cache_key)
        now = time.monotonic()
        if entry is not None and now - entry[1] < _CHAT_CLIENT_TTL_SECONDS:
            return entry[0]
        if entry is not None:
            try:
                await entry[0].close()
            except Exception as exc:
                logger.warning("failed to close expired chat client", error=repr(exc))
            _chat_clients.pop(cache_key, None)
        try:
            pinned = await pin_chat_base_url(base_url)
        except UnsafeOutboundUrlError as exc:
            raise UpstreamError(
                "chat base URL rejected by SSRF check",
                public_message="Chat provider URL was rejected by SSRF protection.",
            ) from exc
        kwargs: dict[str, Any] = {
            "api_key": credential.api_key,
            "timeout": _MODEL_TIMEOUT_SECONDS,
            "base_url": base_url,
            "http_client": pinned_async_client(pinned, timeout=_MODEL_TIMEOUT_SECONDS),
        }
        client = openai_module.AsyncOpenAI(**kwargs)
        _chat_clients[cache_key] = (client, time.monotonic())
        _chat_clients.move_to_end(cache_key)
        while len(_chat_clients) > _CHAT_CLIENTS_MAX:
            _, (evicted, _ts) = _chat_clients.popitem(last=False)
            try:
                await evicted.close()
            except Exception as exc:
                logger.warning("failed to close evicted chat client", error=repr(exc))
        return client


def _should_try_next_credential(
    exc: Exception,
    prepared: PreparedChatTurn,
    credential: ProviderCredential,
) -> bool:
    if credential == prepared.credentials[-1]:
        return False
    return _is_provider_auth_error(exc)


def _is_provider_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return True
    message = str(exc).lower()
    return "invalid_api_key" in message or "incorrect api key" in message


def _provider_error(exc: Exception, credential: ProviderCredential) -> UpstreamError:
    message = _safe_chat_error(exc)
    if _is_provider_auth_error(exc):
        if credential.source == "saved chat key":
            message = (
                "OpenAI rejected the saved chat key. It has been cleared; save a fresh "
                "key generated from the OpenAI API keys page."
            )
        else:
            message = (
                f"OpenAI rejected the {credential.source}. Use a fresh key generated "
                "from the OpenAI API keys page."
            )
    return UpstreamError(message, public_message=message)


def _is_saved_key_auth_error(exc: Exception) -> bool:
    return isinstance(exc, UpstreamError) and str(exc).startswith(
        "OpenAI rejected the saved chat key."
    )
