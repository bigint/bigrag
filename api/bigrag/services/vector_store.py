from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

import boto3
import httpx
from botocore.exceptions import ClientError
from qdrant_client import AsyncQdrantClient, models

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterCondition, FilterExpression

VectorStoreProvider = Literal["qdrant", "s3_vectors", "turbopuffer"]

logger = get_logger("bigrag.vector_store")

_TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
    httpx.HTTPError,
)

_POINT_NAMESPACE = uuid.UUID("1b04f7ca-0c3b-5d76-a5bb-6e4b4a40f61d")
_FIXED_PAYLOAD_FIELDS = {"id", "text", "document_id", "chunk_index", "embedding"}


class VectorStoreFeatureError(RuntimeError):
    pass


class VectorStoreBackend(Protocol):
    provider: VectorStoreProvider
    supports_text_search: bool

    def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None: ...

    async def delete_collection(self, name: str) -> None: ...

    async def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int: ...

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]: ...

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]: ...

    async def delete_by_document(self, collection: str, document_id: str) -> None: ...

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None: ...

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]: ...

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int: ...

    async def export_collection_points(self, collection: str) -> list[dict]: ...


def _backend_name(prefix: str, name: str) -> str:
    return f"{prefix}{name}"


def _point_id(collection: str, value: str) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{collection}:{value}"))


def _build_payload(
    *,
    id_: str,
    document_id: str,
    chunk_index: int,
    text: str,
    metadata: dict | None = None,
) -> dict:
    payload = dict(metadata or {})
    payload.update(
        {
            "id": id_,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": text,
        }
    )
    return payload


def _row_from_payload(point_id: str, score: float, payload: dict) -> dict:
    metadata = {
        k: v for k, v in payload.items() if k not in _FIXED_PAYLOAD_FIELDS and v is not None
    }
    return {
        "id": payload.get("id") or point_id,
        "score": score,
        "text": payload.get("text", ""),
        "document_id": payload.get("document_id"),
        "chunk_index": payload.get("chunk_index"),
        "metadata": metadata,
    }


def _chunk_rows_from_payloads(
    payloads: list[dict],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    all_chunks = sorted(payloads, key=lambda payload: payload.get("chunk_index", 0))
    total = len(all_chunks)
    page = all_chunks[offset : offset + limit]
    return [
        {
            "id": payload.get("id", ""),
            "text": payload.get("text", ""),
            "chunk_index": payload.get("chunk_index", 0),
        }
        for payload in page
    ], total


def _to_qdrant_filter(filters: FilterExpression | None) -> models.Filter | None:
    if filters is None:
        return None
    must: list[models.Condition] = []
    must_not: list[models.Condition] = []
    for condition in filters.conditions:
        if condition.operator == "eq":
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchValue(value=condition.value),
                )
            )
        elif condition.operator == "ne":
            must_not.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchValue(value=condition.value),
                )
            )
        elif condition.operator == "in":
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    match=models.MatchAny(any=condition.value),
                )
            )
        else:
            must.append(
                models.FieldCondition(
                    key=condition.field,
                    range=models.Range(
                        gt=condition.value if condition.operator == "gt" else None,
                        gte=condition.value if condition.operator == "gte" else None,
                        lt=condition.value if condition.operator == "lt" else None,
                        lte=condition.value if condition.operator == "lte" else None,
                    ),
                )
            )
    if not must and not must_not:
        return None
    return models.Filter(must=must or None, must_not=must_not or None)


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


def _to_turbopuffer_filter(filters: FilterExpression | None) -> list | None:
    if filters is None:
        return None
    clauses = [_to_turbopuffer_condition(condition) for condition in filters.conditions]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return ["And", clauses]


def _to_turbopuffer_condition(condition: FilterCondition) -> list:
    op = {
        "eq": "Eq",
        "ne": "NotEq",
        "gt": "Gt",
        "gte": "Gte",
        "lt": "Lt",
        "lte": "Lte",
        "in": "In",
    }[condition.operator]
    return [condition.field, op, condition.value]


class QdrantVectorStore:
    provider: VectorStoreProvider = "qdrant"
    supports_text_search = True

    def __init__(
        self,
        url: str = "http://localhost:6333",
        *,
        api_key: str | None = None,
        connect_timeout_seconds: int | float | None = 10,
        search_ef: int | None = None,
        prefix: str = "bigrag_",
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.client: AsyncQdrantClient | None = None
        self._max_retries: int = 2
        self._connect_timeout_seconds = (
            None
            if connect_timeout_seconds is None or connect_timeout_seconds <= 0
            else float(connect_timeout_seconds)
        )
        self._search_ef = search_ef if search_ef and search_ef > 0 else None
        self.prefix = prefix

    def connect(self) -> None:
        self.client = AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=self._connect_timeout_seconds,
        )
        logger.info("connected to qdrant", url=self.url)

    async def reconnect(self) -> None:
        logger.warning("reconnecting to qdrant", url=self.url)
        await self.close()
        self.connect()
        logger.info("reconnected to qdrant", url=self.url)

    async def _run_with_retry(
        self,
        fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except _TRANSIENT_ERRORS as e:
                last_error = e
                if attempt < self._max_retries:
                    logger.warning(
                        "qdrant transient error",
                        attempt=attempt + 1,
                        max_attempts=self._max_retries + 1,
                        error=repr(e),
                    )
                    await self.reconnect()
                else:
                    raise
            except Exception as e:
                err_str = str(e).lower()
                if any(kw in err_str for kw in ("connect", "timeout", "unavailable", "reset")):
                    last_error = e
                    if attempt < self._max_retries:
                        logger.warning(
                            "qdrant likely transient error",
                            attempt=attempt + 1,
                            max_attempts=self._max_retries + 1,
                            error=repr(e),
                        )
                        await self.reconnect()
                    else:
                        raise
                else:
                    raise
        raise last_error

    async def close(self) -> None:
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("qdrant connection closed")

    async def health_check(self) -> None:
        client = self._client()
        await self._run_with_retry(client.get_collections)

    def _client(self) -> AsyncQdrantClient:
        if self.client is None:
            self.connect()
        if self.client is None:
            raise RuntimeError("Qdrant client is not connected")
        return self.client

    def _col(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    async def _create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        schema: Any,
    ) -> None:
        client = self._client()
        try:
            await self._run_with_retry(
                client.create_payload_index,
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )
        except Exception as exc:
            if "already exists" in str(exc).lower() or "exists" in str(exc).lower():
                return
            logger.warning(
                "vector_store: payload index creation failed",
                collection=collection_name,
                field=field_name,
                error=str(exc),
            )

    async def _ensure_payload_indexes(
        self,
        collection_name: str,
        tenant_field: str | None = None,
    ) -> None:
        text_schema = models.TextIndexParams(
            type=models.TextIndexType.TEXT,
            tokenizer=models.TokenizerType.WORD,
            min_token_len=2,
            lowercase=True,
        )
        indexes: list[tuple[str, Any]] = [
            ("id", "keyword"),
            ("document_id", "keyword"),
            ("chunk_index", "integer"),
            ("char_start", "integer"),
            ("char_end", "integer"),
            ("page_no", "integer"),
            ("text", text_schema),
        ]
        if tenant_field:
            indexes.append((tenant_field, "keyword"))

        await asyncio.gather(
            *[
                self._create_payload_index(collection_name, field_name, schema)
                for field_name, schema in indexes
            ]
        )

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None:
        col = self._col(name)
        client = self._client()

        if not await self._run_with_retry(client.collection_exists, col):
            await self._run_with_retry(
                client.create_collection,
                collection_name=col,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info(
                "created qdrant collection",
                collection=col,
                dimension=dimension,
                index=index_type,
            )

        await self._ensure_payload_indexes(col, tenant_field=tenant_field)

    async def delete_collection(self, name: str) -> None:
        col = self._col(name)
        client = self._client()
        if await self._run_with_retry(client.collection_exists, col):
            await self._run_with_retry(client.delete_collection, col)
            logger.info("dropped qdrant collection", collection=col)

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
        col = self._col(collection)
        points = []
        for i in range(len(ids)):
            points.append(
                models.PointStruct(
                    id=_point_id(col, ids[i]),
                    vector=embeddings[i],
                    payload=_build_payload(
                        id_=ids[i],
                        document_id=document_ids[i],
                        chunk_index=chunk_indices[i],
                        text=texts[i],
                        metadata=metadata[i] if metadata else None,
                    ),
                )
            )

        client = self._client()
        await self._run_with_retry(client.upsert, collection_name=col, points=points, wait=True)
        logger.info("inserted vectors", collection=col, count=len(points))
        return len(points)

    def _search_params(self) -> models.SearchParams | None:
        if self._search_ef is None:
            return None
        return models.SearchParams(hnsw_ef=self._search_ef)

    @staticmethod
    def _row_from_qdrant(point: Any) -> dict:
        payload = dict(getattr(point, "payload", None) or {})
        point_id = str(getattr(point, "id", ""))
        return _row_from_payload(point_id, getattr(point, "score", 0.0), payload)

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        col = self._col(collection)

        client = self._client()
        results = await self._run_with_retry(
            client.query_points,
            collection_name=col,
            query=query_embedding,
            limit=top_k,
            query_filter=_to_qdrant_filter(filters),
            search_params=self._search_params(),
            with_payload=True,
            with_vectors=False,
        )

        hits = [self._row_from_qdrant(point) for point in results.points]
        logger.info("vector search", collection=col, top_k=top_k, hits=len(hits), filters=filters)
        return hits

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        col = self._col(collection)
        client = self._client()
        if not await self._run_with_retry(client.collection_exists, col):
            return [], 0

        results = []
        next_offset = None
        while True:
            batch, next_offset = await self._run_with_retry(
                client.scroll,
                collection_name=col,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
                with_payload=True,
                with_vectors=False,
                limit=10000,
                offset=next_offset,
            )
            results.extend(batch)
            if next_offset is None:
                break
        return _chunk_rows_from_payloads([r.payload or {} for r in results], limit, offset)

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        col = self._col(collection)
        client = self._client()
        if not await self._run_with_retry(client.collection_exists, col):
            return
        await self._run_with_retry(
            client.delete,
            collection_name=col,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            ),
            wait=True,
        )
        logger.info("delete vectors by document", collection=col, document_id=document_id)

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        col = self._col(collection)
        client = self._client()
        point_ids = [_point_id(col, id_) for id_ in ids]
        await self._run_with_retry(
            client.delete,
            collection_name=col,
            points_selector=point_ids,
            wait=True,
        )
        logger.info("delete vectors by ids", collection=col, count=len(ids))

    @staticmethod
    def _combine_filters(
        *filters: models.Filter | None,
    ) -> models.Filter | None:
        active = [f for f in filters if f is not None]
        if not active:
            return None
        if len(active) == 1:
            return active[0]
        return models.Filter(must=active)

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        col = self._col(collection)
        terms = [term for term in query_terms if term]
        if not terms:
            return []

        text_filter = models.Filter(
            should=[
                models.FieldCondition(key="text", match=models.MatchText(text=term))
                for term in terms
            ]
        )
        combined_filter = self._combine_filters(_to_qdrant_filter(filters), text_filter)

        try:
            client = self._client()
            results, _next_offset = await self._run_with_retry(
                client.scroll,
                collection_name=col,
                scroll_filter=combined_filter,
                with_payload=True,
                with_vectors=False,
                limit=top_k * 3,
            )
        except _TRANSIENT_ERRORS:
            raise
        except Exception as exc:
            logger.warning("text search query failed", collection=col, error=repr(exc))
            return []

        logger.info("text search", collection=col, terms=len(terms), hits=len(results))
        return [self._row_from_qdrant(point) for point in results]

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        col = self._col(collection)
        points = []
        for i in range(len(ids)):
            points.append(
                models.PointStruct(
                    id=_point_id(col, ids[i]),
                    vector=embeddings[i],
                    payload=_build_payload(
                        id_=ids[i],
                        document_id="",
                        chunk_index=0,
                        text=texts[i],
                        metadata=metadata[i] if metadata else None,
                    ),
                )
            )

        client = self._client()
        await self._run_with_retry(client.upsert, collection_name=col, points=points, wait=True)
        logger.info("upserted vectors", collection=col, count=len(points))
        return len(points)

    async def export_collection_points(self, collection: str) -> list[dict]:
        col = self._col(collection)
        client = self._client()
        if not await self._run_with_retry(client.collection_exists, col):
            return []
        out = []
        offset = None
        while True:
            points, offset = await client.scroll(
                collection_name=col,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for point in points:
                out.append(
                    {
                        "id": str(getattr(point, "id", "")),
                        "payload": getattr(point, "payload", {}) or {},
                        "vector": getattr(point, "vector", None),
                    }
                )
            if offset is None:
                break
        return out


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


class TurbopufferVectorStore:
    provider: VectorStoreProvider = "turbopuffer"
    supports_text_search = False

    def __init__(
        self,
        *,
        api_key: str | None,
        region: str,
        namespace_prefix: str = "bigrag_",
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.prefix = namespace_prefix or "bigrag_"
        self.client: httpx.AsyncClient | None = None

    def connect(self) -> None:
        if not self.api_key:
            raise RuntimeError("turbopuffer API key is not configured")
        base_url = f"https://{self.region}.turbopuffer.com"
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        logger.info("connected to turbopuffer", region=self.region)

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.connect()
        if self.client is None:
            raise RuntimeError("turbopuffer client is not connected")
        return self.client

    def _namespace(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def health_check(self) -> None:
        client = self._client()
        response = await client.get("/v1/namespaces")
        response.raise_for_status()

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None:
        await self._write(
            name,
            {
                "upsert_rows": [],
                "distance_metric": "cosine_distance",
                "schema": {"vector": {"type": f"[{dimension}]f32", "ann": True}},
            },
        )

    async def delete_collection(self, name: str) -> None:
        client = self._client()
        response = await client.delete(f"/v1/namespaces/{self._namespace(name)}")
        if response.status_code == 404:
            return
        response.raise_for_status()

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
        namespace = self._namespace(collection)
        rows = []
        for i in range(len(ids)):
            payload = _build_payload(
                id_=ids[i],
                document_id=document_ids[i],
                chunk_index=chunk_indices[i],
                text=texts[i],
                metadata=metadata[i] if metadata else None,
            )
            rows.append({"id": _point_id(namespace, ids[i]), "vector": embeddings[i], **payload})
        await self._write(collection, {"upsert_rows": rows, "distance_metric": "cosine_distance"})
        return len(rows)

    async def _write(self, collection: str, payload: dict) -> dict:
        client = self._client()
        response = await client.post(f"/v2/namespaces/{self._namespace(collection)}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else {}

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {
            "rank_by": ["vector", "ANN", query_embedding],
            "top_k": top_k,
            "include_attributes": True,
        }
        turbo_filter = _to_turbopuffer_filter(filters)
        if turbo_filter:
            payload["filters"] = turbo_filter
        client = self._client()
        response = await client.post(
            f"/v2/namespaces/{self._namespace(collection)}/query",
            json=payload,
        )
        response.raise_for_status()
        rows = []
        for row in response.json().get("rows", []):
            point_id = str(row.get("id", ""))
            distance = float(row.get("$dist", 0.0))
            payload_row = {k: v for k, v in row.items() if k not in {"$dist"}}
            rows.append(_row_from_payload(point_id, max(0.0, 1.0 - distance), payload_row))
        return rows

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        rows = await self._query_rows(
            collection,
            {
                "rank_by": ["id", "asc"],
                "filters": ["document_id", "Eq", document_id],
                "limit": {"total": 10000},
                "include_attributes": True,
            },
        )
        return _chunk_rows_from_payloads(rows, limit, offset)

    async def _query_rows(self, collection: str, payload: dict) -> list[dict]:
        client = self._client()
        response = await client.post(
            f"/v2/namespaces/{self._namespace(collection)}/query",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("rows", [])

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        await self._write(collection, {"delete_by_filter": ["document_id", "Eq", document_id]})

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        namespace = self._namespace(collection)
        await self._write(collection, {"deletes": [_point_id(namespace, id_) for id_ in ids]})

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        raise VectorStoreFeatureError("turbopuffer does not support keyword or hybrid search in v1")

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
        rows = await self._query_rows(
            collection,
            {
                "rank_by": ["id", "asc"],
                "limit": {"total": 10000},
                "include_attributes": True,
            },
        )
        points = []
        for row in rows:
            points.append(
                {
                    "id": str(row.get("id", "")),
                    "payload": {k: v for k, v in row.items() if k not in {"id", "vector"}},
                    "vector": row.get("vector"),
                }
            )
        return points


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

    async def export_collection_points(self, collection: str) -> list[dict]:
        return await self.backend.export_collection_points(collection)


vector_store = VectorStore()
