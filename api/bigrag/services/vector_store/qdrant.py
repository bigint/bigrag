from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient, models

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.vector_store.base import (
    VectorStoreProvider,
    _backend_name,
    _build_payload,
    _chunk_rows_from_payloads,
    _point_id,
    _row_from_payload,
)

logger = get_logger("bigrag.vector_store")

_TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
    httpx.HTTPError,
)


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

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> list[dict]:
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
                with_vectors=with_vectors,
            )
            for point in points:
                out.append(
                    {
                        "id": str(getattr(point, "id", "")),
                        "payload": getattr(point, "payload", {}) or {},
                        "vector": getattr(point, "vector", None) if with_vectors else None,
                    }
                )
            if offset is None:
                break
        return out
