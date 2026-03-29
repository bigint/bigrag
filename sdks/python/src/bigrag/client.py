"""Synchronous and asynchronous clients for the bigRAG API."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from bigrag.errors import (
    APIConnectionError,
    APITimeoutError,
    raise_for_status,
)
from bigrag.types import (
    Collection,
    CollectionListResponse,
    Document,
    DocumentListResponse,
    QueryResponse,
)

_DEFAULT_BASE_URL = "http://localhost:8080"
_USER_AGENT = "bigrag-python/0.2.0"


class BigRAG:
    """Synchronous client for the bigRAG RAG platform."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 120.0,
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

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            if attempt > 0:
                time.sleep(min(0.5 * 2**attempt, 4.0))
            try:
                response = self._client.request(
                    method, path, json=json_body, params=params
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

    # Health

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    # Collections

    def list_collections(self) -> CollectionListResponse:
        data = self._request("GET", "/v1/collections")
        return CollectionListResponse.from_dict(data)

    def create_collection(
        self,
        name: str,
        description: str = "",
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        dimension: int | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> Collection:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }
        if embedding_provider:
            body["embedding_provider"] = embedding_provider
        if embedding_model:
            body["embedding_model"] = embedding_model
        if dimension:
            body["dimension"] = dimension
        return Collection(**self._request("POST", "/v1/collections", json_body=body))

    def get_collection(self, name: str) -> Collection:
        return Collection(**self._request("GET", f"/v1/collections/{name}"))

    def delete_collection(self, name: str) -> dict[str, Any]:
        return self._request("DELETE", f"/v1/collections/{name}")

    # Documents

    def upload_document(
        self, collection: str, file_path: str | Path, metadata: dict | None = None
    ) -> Document:
        p = Path(file_path)
        with open(p, "rb") as f:
            files = {"file": (p.name, f)}
            data: dict[str, str] = {}
            if metadata:
                data["metadata"] = json.dumps(metadata)
            response = self._client.post(
                f"/v1/collections/{collection}/documents",
                files=files,
                data=data,
            )
            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise_for_status(response.status_code, body)
            return Document(**response.json())

    def list_documents(
        self, collection: str, status: str | None = None
    ) -> DocumentListResponse:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        data = self._request(
            "GET", f"/v1/collections/{collection}/documents", params=params
        )
        return DocumentListResponse.from_dict(data)

    def get_document(self, collection: str, document_id: str) -> Document:
        return Document(
            **self._request(
                "GET", f"/v1/collections/{collection}/documents/{document_id}"
            )
        )

    def delete_document(self, collection: str, document_id: str) -> dict[str, Any]:
        return self._request(
            "DELETE", f"/v1/collections/{collection}/documents/{document_id}"
        )

    def reprocess_document(self, collection: str, document_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/collections/{collection}/documents/{document_id}/reprocess",
        )

    # Query

    def query(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> QueryResponse:
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if filters:
            body["filters"] = filters
        if min_score is not None:
            body["min_score"] = min_score
        data = self._request(
            "POST", f"/v1/collections/{collection}/query", json_body=body
        )
        return QueryResponse.from_dict(data)

    # Vectors (direct)

    def upsert_vectors(self, collection: str, vectors: list[dict]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/collections/{collection}/vectors/upsert",
            json_body={"vectors": vectors},
        )

    def delete_vectors(self, collection: str, ids: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/v1/collections/{collection}/vectors/delete",
            json_body={"ids": ids},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BigRAG:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncBigRAG:
    """Asynchronous client for the bigRAG RAG platform."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 120.0,
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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            if attempt > 0:
                await asyncio.sleep(min(0.5 * 2**attempt, 4.0))
            try:
                response = await self._client.request(
                    method, path, json=json_body, params=params
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

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def list_collections(self) -> CollectionListResponse:
        data = await self._request("GET", "/v1/collections")
        return CollectionListResponse.from_dict(data)

    async def create_collection(self, name: str, **kwargs: Any) -> Collection:
        body = {"name": name, **kwargs}
        return Collection(**await self._request("POST", "/v1/collections", json_body=body))

    async def get_collection(self, name: str) -> Collection:
        return Collection(**await self._request("GET", f"/v1/collections/{name}"))

    async def delete_collection(self, name: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/v1/collections/{name}")

    async def upload_document(
        self, collection: str, file_path: str | Path, metadata: dict | None = None
    ) -> Document:
        p = Path(file_path)
        with open(p, "rb") as f:
            files = {"file": (p.name, f)}
            data: dict[str, str] = {}
            if metadata:
                data["metadata"] = json.dumps(metadata)
            response = await self._client.post(
                f"/v1/collections/{collection}/documents",
                files=files,
                data=data,
            )
            if response.status_code >= 400:
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                raise_for_status(response.status_code, body)
            return Document(**response.json())

    async def list_documents(
        self, collection: str, status: str | None = None
    ) -> DocumentListResponse:
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        data = await self._request(
            "GET", f"/v1/collections/{collection}/documents", params=params
        )
        return DocumentListResponse.from_dict(data)

    async def delete_document(self, collection: str, document_id: str) -> dict[str, Any]:
        return await self._request(
            "DELETE", f"/v1/collections/{collection}/documents/{document_id}"
        )

    async def query(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
        min_score: float | None = None,
    ) -> QueryResponse:
        body: dict[str, Any] = {"query": query, "top_k": top_k}
        if filters:
            body["filters"] = filters
        if min_score is not None:
            body["min_score"] = min_score
        data = await self._request(
            "POST", f"/v1/collections/{collection}/query", json_body=body
        )
        return QueryResponse.from_dict(data)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncBigRAG:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
