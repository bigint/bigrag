from __future__ import annotations

import asyncio
import os
import random
from typing import Any
from uuid import uuid4

import httpx

from bigrag._errors import (
    APIConnectionError,
    APITimeoutError,
    error_for_status,
)
from bigrag._version import __version__

USER_AGENT = f"bigrag-python/{__version__}"

_DEFAULT_BASE_URL = "http://localhost:4000"
_DEFAULT_TIMEOUT = 120.0
_DEFAULT_MAX_RETRIES = 2
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _buffer_files(files: Any) -> Any:
    if files is None:
        return files
    if isinstance(files, dict):
        return {k: _buffer_one(v) for k, v in files.items()}
    if isinstance(files, list):
        return [(name, _buffer_one(payload)) for name, payload in files]
    return files


def _buffer_one(payload: Any) -> Any:
    if isinstance(payload, tuple):
        filename, fileobj, *rest = payload
        return (filename, _ensure_bytes(fileobj), *rest)
    return _ensure_bytes(payload)


def _ensure_bytes(fileobj: Any) -> Any:
    if hasattr(fileobj, "read"):
        data = fileobj.read()
        if hasattr(fileobj, "close"):
            try:
                fileobj.close()
            except Exception:
                pass
        return data
    return fileobj


def _rewind_files(files: Any) -> None:
    if files is None:
        return
    items = files.values() if isinstance(files, dict) else files
    for entry in items:
        payload = entry[1] if isinstance(entry, tuple) and len(entry) >= 2 else entry
        seek = getattr(payload, "seek", None)
        if callable(seek):
            try:
                seek(0)
            except Exception:
                pass


class BigRAGCore:
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
        self.api_key = (
            api_key if api_key is not None else (os.environ.get("BIGRAG_API_KEY") or "")
        )
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

    async def _execute_with_retry(
        self, send_fn, *, safe_to_retry: bool = False
    ) -> httpx.Response:
        last_error: Exception | None = None
        retry_after_override: float | None = None

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                base_delay = min(0.5 * (2 ** (attempt - 1)), 4.0)
                delay = base_delay * (0.75 + random.random() * 0.5)
                if retry_after_override is not None:
                    delay = max(retry_after_override, delay)
                    retry_after_override = None
                await asyncio.sleep(delay)

            try:
                response = await send_fn()
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

            if (
                response.status_code >= 500
                and attempt < self.max_retries
                and safe_to_retry
            ):
                last_error = Exception(response.text)
                continue

            if response.status_code == 429 and attempt < self.max_retries:
                last_error = Exception("Rate limited")
                retry_after_header = response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        retry_after_override = float(retry_after_header)
                    except (TypeError, ValueError):
                        retry_after_override = None
                continue

            return response

        raise APIConnectionError(str(last_error) if last_error else "Request failed")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._headers()
        if json is not None:
            headers["Content-Type"] = "application/json"

        method_upper = method.upper()
        idem_key = idempotency_key
        if idem_key is None and method_upper in _MUTATING_METHODS:
            idem_key = uuid4().hex
        if idem_key is not None:
            headers["Idempotency-Key"] = idem_key

        safe_to_retry = method_upper in _SAFE_METHODS or idem_key is not None

        async def _send() -> httpx.Response:
            return await self._client.request(
                method,
                url,
                json=json,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )

        response = await self._execute_with_retry(_send, safe_to_retry=safe_to_retry)

        if response.status_code >= 400:
            await self._throw_for_status(response)

        if response.status_code == 204:
            return {"status": "ok"}

        text = response.text
        if not text:
            return {"status": "ok"}

        return response.json()

    async def _request_form(
        self,
        path: str,
        files: Any,
        data: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._headers()

        idem_key = idempotency_key if idempotency_key is not None else uuid4().hex
        headers["Idempotency-Key"] = idem_key

        buffered_files = _buffer_files(files)

        async def _send() -> httpx.Response:
            _rewind_files(buffered_files)
            return await self._client.post(
                url,
                files=buffered_files,
                data=data or {},
                headers=headers,
                timeout=self.timeout,
            )

        response = await self._execute_with_retry(_send, safe_to_retry=True)

        if response.status_code >= 400:
            await self._throw_for_status(response)

        return response.json()

    @staticmethod
    async def _throw_for_status(response: httpx.Response) -> None:
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
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BigRAGCore:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()
