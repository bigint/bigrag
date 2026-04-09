"""Low-level HTTP transport for the bigRAG API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from bigrag._errors import (
    APIConnectionError,
    APITimeoutError,
    error_for_status,
)

USER_AGENT = "bigrag-python/0.0.1"

_DEFAULT_BASE_URL = "http://localhost:6100"
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_MAX_RETRIES = 2


class BigRAGCore:
    """Low-level async HTTP transport with retry, auth, and error handling.

    This class is not usually instantiated directly.  Use :class:`BigRAG`
    instead, which adds high-level resource namespaces on top.
    """

    api_key: str
    base_url: str
    timeout: float
    max_retries: int
    _client: httpx.AsyncClient
    _owns_client: bool

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else (os.environ.get("BIGRAG_API_KEY") or "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
            self._owns_client = True

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": USER_AGENT}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """Issue a JSON request and return the parsed response body.

        Retries on 429, 5xx, and connection/timeout errors using exponential
        back-off: ``min(0.5 * 2^attempt, 4)`` seconds.
        """
        url = f"{self.base_url}{path}"
        headers = self._headers()
        if json is not None:
            headers["Content-Type"] = "application/json"

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                delay = min(0.5 * (2 ** attempt), 4.0)
                await asyncio.sleep(delay)

            try:
                response = await self._client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    continue
                raise APITimeoutError(str(exc)) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    continue
                raise APIConnectionError(str(exc)) from exc

            # Retry on server errors
            if response.status_code >= 500 and attempt < self.max_retries:
                last_error = Exception(response.text)
                continue

            # Retry on rate limit
            if response.status_code == 429 and attempt < self.max_retries:
                last_error = Exception("Rate limited")
                continue

            # Raise typed errors for client/server error codes
            if response.status_code >= 400:
                await self._throw_for_status(response)

            # 204 No Content
            if response.status_code == 204:
                return {"status": "ok"}

            text = response.text
            if not text:
                return {"status": "ok"}

            return response.json()

        raise APIConnectionError(str(last_error) if last_error else "Request failed")

    async def _request_form(
        self,
        path: str,
        files: dict[str, Any],
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Issue a ``multipart/form-data`` POST and return the parsed body."""
        url = f"{self.base_url}{path}"
        headers = self._headers()
        # Do not set Content-Type; httpx sets it automatically with boundary.

        response = await self._client.post(
            url,
            files=files,
            data=data or {},
            headers=headers,
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            await self._throw_for_status(response)

        return response.json()

    @staticmethod
    async def _throw_for_status(response: httpx.Response) -> None:
        """Parse an error body and raise the appropriate exception."""
        try:
            body = response.json()
        except Exception:
            body = {}

        message = (
            body.get("detail")
            or (body.get("error", {}) or {}).get("message")
            or body.get("message")
            or response.reason_phrase
            or "Unknown error"
        )
        code = (body.get("error", {}) or {}).get("code")
        raise error_for_status(response.status_code, message, code)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BigRAGCore:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
