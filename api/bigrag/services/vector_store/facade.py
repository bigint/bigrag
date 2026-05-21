from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.vector_store.base import VectorStoreBackend
from bigrag.services.vector_store.turbopuffer import TurbopufferVectorStore


class VectorStore:
    def __init__(self) -> None:
        self._backend_instance: VectorStoreBackend = TurbopufferVectorStore()
        self.client: Any | None = None
        self._condition = asyncio.Condition()
        self._active = 0
        self._swapping = False

    def is_configured(self) -> bool:
        return bool(getattr(self.backend, "api_key", None))

    @property
    def backend(self) -> VectorStoreBackend:
        return self._backend_instance

    @backend.setter
    def backend(self, value: VectorStoreBackend) -> None:
        self._backend_instance = value
        self._sync_client()

    def configure(
        self,
        url: str | None = None,
        *,
        turbopuffer_api_key: str | None = None,
        turbopuffer_region: str = "aws-us-east-1",
        turbopuffer_namespace_prefix: str = "bigrag_",
        turbopuffer_base_url: str | None = None,
        **_: Any,
    ) -> None:
        self.backend = TurbopufferVectorStore(
            api_key=turbopuffer_api_key,
            region=turbopuffer_region or "aws-us-east-1",
            namespace_prefix=turbopuffer_namespace_prefix,
            base_url=turbopuffer_base_url,
        )

    def connect(self) -> None:
        self.backend.connect()
        self._sync_client()

    async def close(self) -> None:
        async with self._condition:
            self._swapping = True
            try:
                while self._active:
                    await self._condition.wait()
                await self.backend.close()
                self._sync_client()
            finally:
                self._swapping = False
                self._condition.notify_all()

    async def replace_with(self, other: VectorStore) -> None:
        async with self._condition:
            self._swapping = True
            while self._active:
                await self._condition.wait()
            old_backend = self.backend
            self.backend = other.backend
            self._sync_client()
            try:
                await old_backend.close()
            except Exception:
                pass
            self._swapping = False
            self._condition.notify_all()

    @asynccontextmanager
    async def _backend(self) -> AsyncIterator[VectorStoreBackend]:
        async with self._condition:
            while self._swapping:
                await self._condition.wait()
            self._active += 1
            backend = self.backend
        try:
            yield backend
        finally:
            async with self._condition:
                self._active -= 1
                if self._active == 0:
                    self._condition.notify_all()

    async def health_check(self) -> None:
        async with self._backend() as backend:
            await backend.health_check()

    def _client(self) -> Any:
        client = getattr(self.backend, "client", None)
        if client is None:
            self.backend.connect()
            client = getattr(self.backend, "client", None)
        return client

    def _sync_client(self) -> None:
        self.client = getattr(self.backend, "client", None)

    async def create_collection(
        self,
        name: str,
        dimension: int,
        tenant_field: str | None = None,
    ) -> None:
        async with self._backend() as backend:
            await backend.create_collection(name, dimension, tenant_field)

    async def delete_collection(
        self,
        name: str,
    ) -> None:
        async with self._backend() as backend:
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
    ) -> int:
        async with self._backend() as backend:
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
        payload_fields: list[str] | None = None,
    ) -> list[dict]:
        async with self._backend() as backend:
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
    ) -> tuple[list[dict], int]:
        async with self._backend() as backend:
            return await backend.get_chunks(collection, document_id, limit, offset)

    async def delete_by_document(
        self,
        collection: str,
        document_id: str,
    ) -> None:
        async with self._backend() as backend:
            await backend.delete_by_document(collection, document_id)

    async def delete_by_ids(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        async with self._backend() as backend:
            await backend.delete_by_ids(collection, ids)

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        async with self._backend() as backend:
            return await backend.text_search(collection, query_terms, top_k, filters)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        async with self._backend() as backend:
            return await backend.upsert(collection, ids, embeddings, texts, metadata)

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> list[dict]:
        async with self._backend() as backend:
            return await backend.export_collection_points(collection, with_vectors=with_vectors)

    async def iter_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
        **_: Any,
    ):
        async with self._backend() as backend:
            async for point in backend.iter_collection_points(
                collection,
                with_vectors=with_vectors,
            ):
                yield point


vector_store = VectorStore()
