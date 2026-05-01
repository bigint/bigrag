from __future__ import annotations

from typing import Literal

import httpx

from bigrag.logging import get_logger

logger = get_logger("bigrag.services.credential_check")

Provider = Literal["openai", "openai_compatible", "cohere", "voyage"]

_DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "cohere": "https://api.cohere.ai/v1",
    "voyage": "https://api.voyageai.com/v1",
}


class CredentialCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _build_client(timeout: float) -> httpx.AsyncClient:

    return httpx.AsyncClient(timeout=timeout)


async def verify_provider_credentials(
    provider: Provider,
    api_key: str,
    base_url: str | None,
    *,
    model: str | None = None,
    timeout_seconds: float = 5.0,
) -> None:

    if provider == "openai_compatible" and not base_url:
        raise CredentialCheckError(
            "MISSING_BASE_URL",
            "base_url is required for OpenAI-compatible embedding providers.",
        )
    if provider == "voyage":
        await _verify_voyage(api_key, base_url, model, timeout_seconds)
        return
    await _verify_via_models_listing(provider, api_key, base_url, timeout_seconds)


async def _verify_via_models_listing(
    provider: Provider,
    api_key: str,
    base_url: str | None,
    timeout_seconds: float,
) -> None:
    root = (base_url or _DEFAULT_BASE_URLS[provider]).rstrip("/")
    url = f"{root}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with _build_client(timeout_seconds) as client:
            response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        logger.warning(
            "credential_check timeout", extra={"provider": provider, "base_url": base_url}
        )
        raise CredentialCheckError(
            "TIMEOUT", f"Provider did not respond within {timeout_seconds:.0f}s."
        ) from None
    except httpx.HTTPError as exc:
        logger.warning(
            "credential_check unreachable",
            extra={"provider": provider, "base_url": base_url, "error": type(exc).__name__},
        )
        raise CredentialCheckError("UNREACHABLE", "Could not reach provider.") from None

    status = response.status_code
    if 200 <= status < 300:
        return

    if status in (401, 403):
        logger.info(
            "credential_check rejected",
            extra={"provider": provider, "base_url": base_url, "status": status},
        )
        raise CredentialCheckError("INVALID_KEY", "Invalid API key.")
    if status == 404:
        logger.info(
            "credential_check endpoint missing",
            extra={"provider": provider, "base_url": base_url},
        )
        raise CredentialCheckError("NOT_FOUND", "Provider endpoint did not recognize /models.")
    logger.warning(
        "credential_check provider error",
        extra={"provider": provider, "base_url": base_url, "status": status},
    )
    raise CredentialCheckError("PROVIDER_ERROR", f"Provider returned {status}.")


async def _verify_voyage(
    api_key: str,
    base_url: str | None,
    model: str | None,
    timeout_seconds: float,
) -> None:
    root = (base_url or _DEFAULT_BASE_URLS["voyage"]).rstrip("/")
    url = f"{root}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"input": ["ping"], "model": model or "voyage-3.5"}

    try:
        async with _build_client(timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException:
        logger.warning(
            "credential_check timeout", extra={"provider": "voyage", "base_url": base_url}
        )
        raise CredentialCheckError(
            "TIMEOUT", f"Provider did not respond within {timeout_seconds:.0f}s."
        ) from None
    except httpx.HTTPError as exc:
        logger.warning(
            "credential_check unreachable",
            extra={"provider": "voyage", "base_url": base_url, "error": type(exc).__name__},
        )
        raise CredentialCheckError("UNREACHABLE", "Could not reach provider.") from None

    status = response.status_code
    if 200 <= status < 300:
        return

    if status in (401, 403):
        logger.info(
            "credential_check rejected",
            extra={"provider": "voyage", "base_url": base_url, "status": status},
        )
        raise CredentialCheckError("INVALID_KEY", "Invalid API key.")
    detail = _voyage_error_detail(response)
    logger.warning(
        "credential_check provider error",
        extra={"provider": "voyage", "base_url": base_url, "status": status},
    )
    raise CredentialCheckError(
        "PROVIDER_ERROR", f"Voyage returned {status}{f': {detail}' if detail else '.'}"
    )


def _voyage_error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        for key in ("detail", "error", "message"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                msg = value.get("message")
                if isinstance(msg, str) and msg:
                    return msg
    return ""
