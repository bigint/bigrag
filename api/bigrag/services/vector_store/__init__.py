from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from bigrag.config import settings as _app_settings
from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.vector_store.base import (
    VectorStoreBackend,
    VectorStoreFeatureError,
    VectorStoreProvider,
)
from bigrag.services.vector_store.qdrant import QdrantVectorStore
from bigrag.services.vector_store.turbopuffer import TurbopufferVectorStore

logger = get_logger("bigrag.vector_store")

_PROVIDERS: tuple[VectorStoreProvider, ...] = ("qdrant", "turbopuffer")

__all__ = [
    "VectorStore",
    "VectorStoreFeatureError",
    "VectorStoreProvider",
    "vector_store",
]


class VectorStore:
    def __init__(self) -> None:
        self.provider: str = "collection"
        self.backends: dict[VectorStoreProvider, VectorStoreBackend] = {}
        self._configured_providers: set[VectorStoreProvider] = {"qdrant"}
        self._fallback_provider: VectorStoreProvider = "qdrant"
        self.backend = QdrantVectorStore()
        self.client: Any | None = None
        self._condition = asyncio.Condition()
        self._active = 0
        self._swapping = False

    @property
    def backend(self) -> VectorStoreBackend:
        return self.backends[self._fallback_provider]

    @backend.setter
    def backend(self, value: VectorStoreBackend) -> None:
        provider = _validate_provider(getattr(value, "provider", self._fallback_provider))
        self.backends[provider] = value
        self._fallback_provider = provider
        self._configured_providers.add(provider)
        self._sync_client()

    def configure(
        self,
        url: str | None = None,
        *,
        provider: VectorStoreProvider | None = None,
        connect_timeout_seconds: int | float | None = 10,
        search_ef: int | None = None,
        qdrant_url: str | None = None,
        qdrant_prefer_grpc: bool | None = None,
        qdrant_grpc_port: int | None = None,
        turbopuffer_api_key: str | None = None,
        turbopuffer_region: str = "aws-us-east-1",
        turbopuffer_namespace_prefix: str = "bigrag_",
    ) -> None:
        if provider is not None:
            _validate_provider(provider)
        prefer_grpc = (
            qdrant_prefer_grpc
            if qdrant_prefer_grpc is not None
            else _app_settings.qdrant_prefer_grpc
        )
        grpc_port = (
            qdrant_grpc_port if qdrant_grpc_port is not None else _app_settings.qdrant_grpc_port
        )
        self.backends = {
            "qdrant": QdrantVectorStore(
                qdrant_url or url or "http://localhost:6333",
                connect_timeout_seconds=connect_timeout_seconds,
                search_ef=search_ef,
                prefer_grpc=prefer_grpc,
                grpc_port=grpc_port,
            ),
            "turbopuffer": TurbopufferVectorStore(
                api_key=turbopuffer_api_key,
                region=turbopuffer_region,
                namespace_prefix=turbopuffer_namespace_prefix,
            ),
        }
        self._configured_providers = {"qdrant"}
        if turbopuffer_api_key or provider == "turbopuffer":
            self._configured_providers.add("turbopuffer")
        self._fallback_provider = provider or "qdrant"
        self.provider = provider or "collection"
        self._sync_client()

    def supports_text_search_for(self, provider: VectorStoreProvider | None = None) -> bool:
        return self.backends[
            _validate_provider(provider or self._fallback_provider)
        ].supports_text_search

    @property
    def configured_providers(self) -> tuple[VectorStoreProvider, ...]:
        return tuple(provider for provider in _PROVIDERS if provider in self._configured_providers)

    def connect(self) -> None:
        for provider in self.configured_providers:
            self.backends[provider].connect()
        self._sync_client()

    async def close(self) -> None:
        async with self._condition:
            self._swapping = True
            try:
                while self._active:
                    await self._condition.wait()
                await _close_backends(self.backends)
                self._sync_client()
            finally:
                self._swapping = False
                self._condition.notify_all()

    async def replace_with(self, other: VectorStore) -> None:
        async with self._condition:
            self._swapping = True
            while self._active:
                await self._condition.wait()
            old_backends = dict(self.backends)
            self.provider = other.provider
            self.backends = dict(other.backends)
            self._configured_providers = set(other._configured_providers)
            self._fallback_provider = other._fallback_provider
            self._sync_client()
            await _close_backends(old_backends, log_errors=True)
            self._swapping = False
            self._condition.notify_all()

    @asynccontextmanager
    async def _backend(self, provider: VectorStoreProvider) -> AsyncIterator[VectorStoreBackend]:
        async with self._condition:
            while self._swapping:
                await self._condition.wait()
            self._active += 1
            backend = self.backends[provider]
        try:
            yield backend
        finally:
            async with self._condition:
                self._active -= 1
                if self._active == 0:
                    self._condition.notify_all()

    async def health_check(self) -> None:
        errors: list[str] = []
        for provider in self.configured_providers:
            try:
                async with self._backend(provider) as backend:
                    await backend.health_check()
            except Exception as exc:
                logger.warning(
                    "vector store provider unhealthy",
                    provider=provider,
                    error_type=type(exc).__name__,
                )
                errors.append(f"{provider}: {type(exc).__name__}")
        if errors:
            raise RuntimeError("; ".join(errors))

    async def provider_health(self) -> dict[str, dict[str, object]]:
        results: dict[str, dict[str, object]] = {}
        for provider in _PROVIDERS:
            configured = provider in self._configured_providers
            if not configured:
                results[provider] = {"configured": False, "status": "not_configured", "error": None}
                continue
            try:
                async with self._backend(provider) as backend:
                    await backend.health_check()
                results[provider] = {"configured": True, "status": "ok", "error": None}
            except Exception as exc:
                logger.warning(
                    "vector store provider_health error",
                    provider=provider,
                    error_type=type(exc).__name__,
                )
                results[provider] = {
                    "configured": True,
                    "status": "error",
                    "error": sanitize_message_text(type(exc).__name__),
                }
        return results

    def _client(self, provider: VectorStoreProvider | None = None) -> Any:
        backend = self.backends[_validate_provider(provider or self._fallback_provider)]
        if isinstance(backend, QdrantVectorStore):
            return backend._client()
        client = getattr(backend, "client", None)
        if client is None:
            backend.connect()
            client = getattr(backend, "client", None)
        return client

    async def _provider_for(
        self,
        collection: str,
        provider: VectorStoreProvider | None,
    ) -> VectorStoreProvider:
        if provider is not None:
            return _validate_provider(provider)
        try:
            from bigrag.services.collection_cache import get_or_404

            value = (await get_or_404(collection)).get("vector_store_provider")
            if value:
                return _validate_provider(str(value))
        except Exception:
            return self._fallback_provider
        return self._fallback_provider

    def _sync_client(self) -> None:
        fallback = self.backends.get(self._fallback_provider)
        self.client = getattr(fallback, "client", None)
        if self.client is not None:
            return
        for provider in self.configured_providers:
            client = getattr(self.backends[provider], "client", None)
            if client is not None:
                self.client = client
                return

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
        provider: VectorStoreProvider | None = None,
    ) -> None:
        selected_provider = await self._provider_for(name, provider)
        async with self._backend(selected_provider) as backend:
            await backend.create_collection(name, dimension, index_type, tenant_field)

    async def delete_collection(
        self,
        name: str,
        provider: VectorStoreProvider | None = None,
    ) -> None:
        selected_provider = await self._provider_for(name, provider)
        async with self._backend(selected_provider) as backend:
            await backend.delete_collection(name)

    async def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
        provider: VectorStoreProvider | None = None,
    ) -> int:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.insert(
                collection,
                ids,
                document_ids,
                chunk_indices,
                texts,
                embeddings,
                metadata,
            )

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
        provider: VectorStoreProvider | None = None,
        payload_fields: list[str] | None = None,
    ) -> list[dict]:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.search(
                collection,
                query_embedding,
                top_k,
                filters,
                payload_fields=payload_fields,
            )

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
        provider: VectorStoreProvider | None = None,
    ) -> tuple[list[dict], int]:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.get_chunks(collection, document_id, limit, offset)

    async def delete_by_document(
        self,
        collection: str,
        document_id: str,
        provider: VectorStoreProvider | None = None,
    ) -> None:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            await backend.delete_by_document(collection, document_id)

    async def delete_by_ids(
        self,
        collection: str,
        ids: list[str],
        provider: VectorStoreProvider | None = None,
    ) -> None:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            await backend.delete_by_ids(collection, ids)

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
        provider: VectorStoreProvider | None = None,
    ) -> list[dict]:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.text_search(collection, query_terms, top_k, filters)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
        provider: VectorStoreProvider | None = None,
    ) -> int:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.upsert(collection, ids, embeddings, texts, metadata)

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
        provider: VectorStoreProvider | None = None,
    ) -> list[dict]:
        selected_provider = await self._provider_for(collection, provider)
        async with self._backend(selected_provider) as backend:
            return await backend.export_collection_points(collection, with_vectors=with_vectors)


def _validate_provider(value: str) -> VectorStoreProvider:
    if value not in _PROVIDERS:
        raise ValueError(f"Unsupported vector store provider: {value}")
    return cast(VectorStoreProvider, value)


async def _close_backends(
    backends: dict[VectorStoreProvider, VectorStoreBackend],
    *,
    log_errors: bool = False,
) -> None:
    seen: set[int] = set()
    for backend in backends.values():
        ident = id(backend)
        if ident in seen:
            continue
        seen.add(ident)
        try:
            await backend.close()
        except Exception as exc:
            if log_errors:
                logger.warning("old vector store close failed", error=str(exc))
            else:
                raise


vector_store = VectorStore()
