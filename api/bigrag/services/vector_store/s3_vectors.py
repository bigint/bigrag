from __future__ import annotations

import asyncio
from typing import Any

import boto3
from botocore.exceptions import ClientError

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.vector_store.base import (
    VectorStoreFeatureError,
    VectorStoreProvider,
    _backend_name,
    _build_payload,
    _chunk_rows_from_payloads,
    _point_id,
    _row_from_payload,
)

logger = get_logger("bigrag.vector_store")


def _to_s3_filter(filters: FilterExpression | None) -> dict | None:
    if filters is None:
        return None
    clauses: list[dict] = []
    for condition in filters.conditions:
        op = "$in" if condition.operator == "in" else f"${condition.operator}"
        clauses.append({condition.field: {op: condition.value}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class S3VectorsStore:
    provider: VectorStoreProvider = "s3_vectors"
    supports_text_search = False

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        index_prefix: str = "bigrag_",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.prefix = index_prefix or "bigrag_"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.client: Any | None = None

    def connect(self) -> None:
        kwargs: dict[str, Any] = {"region_name": self.region}
        if self.access_key_id and self.secret_access_key:
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key
        self.client = boto3.client("s3vectors", **kwargs)
        logger.info("connected to s3 vectors", bucket=self.bucket, region=self.region)

    def _client(self) -> Any:
        if self.client is None:
            self.connect()
        return self.client

    def _index(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    async def close(self) -> None:
        client = self.client
        if client is not None and hasattr(client, "close"):
            await asyncio.to_thread(client.close)
        self.client = None

    async def health_check(self) -> None:
        if not self.bucket:
            raise RuntimeError("S3 Vectors bucket is not configured")
        client = self._client()
        await asyncio.to_thread(client.list_indexes, vectorBucketName=self.bucket, maxResults=1)

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None:
        client = self._client()
        index = self._index(name)
        try:
            await asyncio.to_thread(
                client.create_index,
                vectorBucketName=self.bucket,
                indexName=index,
                dataType="float32",
                dimension=dimension,
                distanceMetric="cosine",
                metadataConfiguration={"nonFilterableMetadataKeys": ["text"]},
            )
            logger.info("created s3 vectors index", index=index, dimension=dimension)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"ConflictException", "ResourceAlreadyExistsException"}:
                return
            if "exists" in str(exc).lower():
                return
            raise

    async def delete_collection(self, name: str) -> None:
        client = self._client()
        try:
            await asyncio.to_thread(
                client.delete_index,
                vectorBucketName=self.bucket,
                indexName=self._index(name),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") == "NotFoundException":
                return
            raise

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
        index = self._index(collection)
        vectors = []
        for i in range(len(ids)):
            vectors.append(
                {
                    "key": _point_id(index, ids[i]),
                    "data": {"float32": [float(v) for v in embeddings[i]]},
                    "metadata": _build_payload(
                        id_=ids[i],
                        document_id=document_ids[i],
                        chunk_index=chunk_indices[i],
                        text=texts[i],
                        metadata=metadata[i] if metadata else None,
                    ),
                }
            )
        await self._put_vectors(index, vectors)
        return len(vectors)

    async def _put_vectors(self, index: str, vectors: list[dict]) -> None:
        client = self._client()
        for start in range(0, len(vectors), 500):
            await asyncio.to_thread(
                client.put_vectors,
                vectorBucketName=self.bucket,
                indexName=index,
                vectors=vectors[start : start + 500],
            )

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        client = self._client()
        kwargs: dict[str, Any] = {
            "vectorBucketName": self.bucket,
            "indexName": self._index(collection),
            "topK": top_k,
            "queryVector": {"float32": [float(v) for v in query_embedding]},
            "returnMetadata": True,
            "returnDistance": True,
        }
        s3_filter = _to_s3_filter(filters)
        if s3_filter:
            kwargs["filter"] = s3_filter
        response = await asyncio.to_thread(client.query_vectors, **kwargs)
        rows = []
        for item in response.get("vectors", []):
            distance = float(item.get("distance", 0.0))
            rows.append(
                _row_from_payload(
                    str(item.get("key", "")),
                    max(0.0, 1.0 - distance),
                    dict(item.get("metadata") or {}),
                )
            )
        return rows

    async def _list_vectors(self, collection: str, *, return_data: bool = False) -> list[dict]:
        client = self._client()
        index = self._index(collection)
        out: list[dict] = []
        token = None
        while True:
            kwargs: dict[str, Any] = {
                "vectorBucketName": self.bucket,
                "indexName": index,
                "maxResults": 500,
                "returnData": return_data,
                "returnMetadata": True,
            }
            if token:
                kwargs["nextToken"] = token
            response = await asyncio.to_thread(client.list_vectors, **kwargs)
            out.extend(response.get("vectors", []))
            token = response.get("nextToken")
            if not token:
                return out

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        vectors = await self._list_vectors(collection)
        payloads = [
            dict(item.get("metadata") or {})
            for item in vectors
            if (item.get("metadata") or {}).get("document_id") == document_id
        ]
        return _chunk_rows_from_payloads(payloads, limit, offset)

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        vectors = await self._list_vectors(collection)
        keys = [
            str(item.get("key"))
            for item in vectors
            if (item.get("metadata") or {}).get("document_id") == document_id
        ]
        await self._delete_keys(collection, keys)

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        index = self._index(collection)
        await self._delete_keys(collection, [_point_id(index, id_) for id_ in ids])

    async def _delete_keys(self, collection: str, keys: list[str]) -> None:
        if not keys:
            return
        client = self._client()
        for start in range(0, len(keys), 500):
            await asyncio.to_thread(
                client.delete_vectors,
                vectorBucketName=self.bucket,
                indexName=self._index(collection),
                keys=keys[start : start + 500],
            )

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        raise VectorStoreFeatureError("s3_vectors does not support keyword or hybrid search in v1")

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        return await self.insert(
            collection,
            ids,
            [""] * len(ids),
            [0] * len(ids),
            texts,
            embeddings,
            metadata,
        )

    async def export_collection_points(self, collection: str) -> list[dict]:
        points = []
        for item in await self._list_vectors(collection, return_data=True):
            points.append(
                {
                    "id": str(item.get("key", "")),
                    "payload": item.get("metadata") or {},
                    "vector": (item.get("data") or {}).get("float32"),
                }
            )
        return points
