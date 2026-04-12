"""Live credential verification for embedding provider API keys.

Called from the admin ``POST /v1/admin/embedding-presets`` handler before
the preset is persisted, so operators learn immediately when a key is bad
instead of hitting the failure at first-use.

The check is intentionally cheap: a single GET against the provider's
``/models`` listing. That proves the key authenticates; it does not prove
the requested ``model`` exists on the provider (mismatches surface at
embed time).

Strictly fails closed — any non-2xx, network error, or timeout raises
``CredentialCheckError``. Self-hosted OpenAI-compatible endpoints must
serve ``/models``; if they do not, the operator must fix the endpoint
rather than bypass verification.
"""

from __future__ import annotations

from typing import Literal

import httpx

from bigrag.logging import get_logger

logger = get_logger("bigrag.services.credential_check")

Provider = Literal["openai", "cohere"]

_DEFAULT_BASE_URLS: dict[Provider, str] = {
    "openai": "https://api.openai.com/v1",
    "cohere": "https://api.cohere.ai/v1",
}


class CredentialCheckError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _build_client(timeout: float) -> httpx.AsyncClient:
    """Seam for tests to inject an httpx.MockTransport."""
    return httpx.AsyncClient(timeout=timeout)


async def verify_provider_credentials(
    provider: Provider,
    api_key: str,
    base_url: str | None,
    *,
    timeout_seconds: float = 5.0,
) -> None:
    """Hit the provider's /models endpoint. Return None on 2xx.

    Raises :class:`CredentialCheckError` on any non-2xx response, network
    failure, or timeout. The ``api_key`` is never logged, even on error.
    """
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
