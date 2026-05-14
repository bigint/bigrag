from __future__ import annotations

from typing import Any

from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.vector_store.base import (
    VectorStoreBackend,
    VectorStoreFeatureError,
    VectorStoreProvider,
)
from bigrag.services.vector_store.qdrant import QdrantVectorStore, _to_qdrant_filter
from bigrag.services.vector_store.s3_vectors import S3VectorsStore, _to_s3_filter
from bigrag.services.vector_store.turbopuffer import (
    TurbopufferVectorStore,
    _to_turbopuffer_filter,
)

__all__ = [
    "QdrantVectorStore",
    "S3VectorsStore",
    "TurbopufferVectorStore",
    "VectorStore",
    "VectorStoreBackend",
    "VectorStoreFeatureError",
    "VectorStoreProvider",
    "_to_qdrant_filter",
    "_to_s3_filter",
    "_to_turbopuffer_filter",
    "vector_store",
]


class VectorStore:
    def __init__(self) -> None:
        self.provider: VectorStoreProvider = "qdrant"
        self.backend: VectorStoreBackend = QdrantVectorStore()
        self.client: Any | None = None

    def configure(
        self,
        url: str | None = None,
        *,
        provider: VectorStoreProvider = "qdrant",
        api_key: str | None = None,
        connect_timeout_seconds: int | float | None = 10,
        search_ef: int | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        s3_vectors_bucket: str = "",
        s3_vectors_region: str = "us-east-1",
        s3_vectors_index_prefix: str = "bigrag_",
        s3_vectors_access_key_id: str | None = None,
        s3_vectors_secret_access_key: str | None = None,
        turbopuffer_api_key: str | None = None,
        turbopuffer_region: str = "aws-us-east-1",
        turbopuffer_namespace_prefix: str = "bigrag_",
    ) -> None:
        self.provider = provider
        if provider == "qdrant":
            self.backend = QdrantVectorStore(
                qdrant_url or url or "http://localhost:6333",
                api_key=qdrant_api_key if qdrant_api_key is not None else api_key,
                connect_timeout_seconds=connect_timeout_seconds,
                search_ef=search_ef,
            )
        elif provider == "s3_vectors":
            self.backend = S3VectorsStore(
                bucket=s3_vectors_bucket,
                region=s3_vectors_region,
                index_prefix=s3_vectors_index_prefix,
                access_key_id=s3_vectors_access_key_id,
                secret_access_key=s3_vectors_secret_access_key,
            )
        elif provider == "turbopuffer":
            self.backend = TurbopufferVectorStore(
                api_key=turbopuffer_api_key,
                region=turbopuffer_region,
                namespace_prefix=turbopuffer_namespace_prefix,
            )
        else:
            raise ValueError(f"Unsupported vector store provider: {provider}")
        self.client = getattr(self.backend, "client", None)

    @property
    def supports_text_search(self) -> bool:
        return self.backend.supports_text_search

    def connect(self) -> None:
        self.backend.connect()
        self.client = getattr(self.backend, "client", None)

    async def close(self) -> None:
        await self.backend.close()
        self.client = getattr(self.backend, "client", None)

    async def health_check(self) -> None:
        await self.backend.health_check()

    def _client(self) -> Any:
        if isinstance(self.backend, QdrantVectorStore):
            return self.backend._client()
        client = getattr(self.backend, "client", None)
        if client is None:
            self.backend.connect()
            client = getattr(self.backend, "client", None)
        return client

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None:
        await self.backend.create_collection(name, dimension, index_type, tenant_field)

    async def delete_collection(self, name: str) -> None:
        await self.backend.delete_collection(name)

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
        return await self.backend.insert(
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
    ) -> list[dict]:
        return await self.backend.search(collection, query_embedding, top_k, filters)

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        return await self.backend.get_chunks(collection, document_id, limit, offset)

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        await self.backend.delete_by_document(collection, document_id)

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        await self.backend.delete_by_ids(collection, ids)

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        return await self.backend.text_search(collection, query_terms, top_k, filters)

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        return await self.backend.upsert(collection, ids, embeddings, texts, metadata)

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> list[dict]:
        return await self.backend.export_collection_points(collection, with_vectors=with_vectors)


vector_store = VectorStore()
