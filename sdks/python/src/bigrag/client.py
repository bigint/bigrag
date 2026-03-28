"""Synchronous and asynchronous clients for the bigRAG API."""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import httpx

from bigrag.errors import (
    APIConnectionError,
    APITimeoutError,
    raise_for_status,
)
from bigrag.namespace import AsyncNamespace, Namespace
from bigrag.types import NamespaceListResponse

_DEFAULT_BASE_URL = "http://localhost:8080"
_USER_AGENT = "bigrag-python/0.1.0"


class BigRAG:
    """Synchronous client for the bigRAG vector database."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("BIGRAG_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": _USER_AGENT}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # -- low-level helpers -----------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            if attempt > 0:
                time.sleep(min(0.5 * 2**attempt, 4.0))
            try:
                response = self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.ConnectError as exc:
                last_exc = exc
                continue

            if response.status_code >= 500 and attempt < self.max_retries:
                last_exc = Exception(response.text)
                continue

            if response.status_code == 429 and attempt < self.max_retries:
                last_exc = Exception(response.text)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise_for_status(response.status_code, body)

            if response.status_code == 204 or not response.content:
                return {"status": "ok"}
            return response.json()

        if isinstance(last_exc, httpx.TimeoutException):
            raise APITimeoutError(str(last_exc))
        if isinstance(last_exc, httpx.ConnectError):
            raise APIConnectionError(str(last_exc))
        raise APIConnectionError(str(last_exc))

    def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(
        self, path: str, *, json: Any = None
    ) -> dict[str, Any]:
        return self._request("POST", path, json=json)

    def _put(
        self, path: str, *, json: Any = None
    ) -> dict[str, Any]:
        return self._request("PUT", path, json=json)

    def _delete(self, path: str) -> dict[str, Any]:
        return self._request("DELETE", path)

    # -- public API ------------------------------------------------------------

    def namespace(self, name: str) -> Namespace:
        """Return a :class:`Namespace` handle for *name*."""
        return Namespace(self, name)

    def namespaces(
        self,
        *,
        prefix: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> NamespaceListResponse:
        """List namespaces."""
        params: dict[str, Any] = {"page_size": page_size}
        if prefix is not None:
            params["prefix"] = prefix
        if cursor is not None:
            params["cursor"] = cursor
        data = self._get("/v1/namespaces", params=params)
        return NamespaceListResponse.from_dict(data)

    def health(self) -> dict[str, Any]:
        """Check API health."""
        return self._get("/health")

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> BigRAG:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncBigRAG:
    """Asynchronous client for the bigRAG vector database."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("BIGRAG_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"User-Agent": _USER_AGENT}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # -- low-level helpers -----------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            if attempt > 0:
                await asyncio.sleep(min(0.5 * 2**attempt, 4.0))
            try:
                response = await self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.ConnectError as exc:
                last_exc = exc
                continue

            if response.status_code >= 500 and attempt < self.max_retries:
                last_exc = Exception(response.text)
                continue

            if response.status_code == 429 and attempt < self.max_retries:
                last_exc = Exception(response.text)
                continue

            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise_for_status(response.status_code, body)

            if response.status_code == 204 or not response.content:
                return {"status": "ok"}
            return response.json()

        if isinstance(last_exc, httpx.TimeoutException):
            raise APITimeoutError(str(last_exc))
        if isinstance(last_exc, httpx.ConnectError):
            raise APIConnectionError(str(last_exc))
        raise APIConnectionError(str(last_exc))

    async def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _post(
        self, path: str, *, json: Any = None
    ) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def _put(
        self, path: str, *, json: Any = None
    ) -> dict[str, Any]:
        return await self._request("PUT", path, json=json)

    async def _delete(self, path: str) -> dict[str, Any]:
        return await self._request("DELETE", path)

    # -- public API ------------------------------------------------------------

    def namespace(self, name: str) -> AsyncNamespace:
        """Return an :class:`AsyncNamespace` handle for *name*."""
        return AsyncNamespace(self, name)

    async def namespaces(
        self,
        *,
        prefix: Optional[str] = None,
        cursor: Optional[str] = None,
        page_size: int = 100,
    ) -> NamespaceListResponse:
        """List namespaces."""
        params: dict[str, Any] = {"page_size": page_size}
        if prefix is not None:
            params["prefix"] = prefix
        if cursor is not None:
            params["cursor"] = cursor
        data = await self._get("/v1/namespaces", params=params)
        return NamespaceListResponse.from_dict(data)

    async def health(self) -> dict[str, Any]:
        """Check API health."""
        return await self._get("/health")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncBigRAG:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
