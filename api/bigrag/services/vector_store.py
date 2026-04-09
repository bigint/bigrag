"""Async wrapper around pymilvus MilvusClient. All blocking calls run in a thread pool."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from pymilvus import DataType, MilvusClient

from bigrag.logging import get_logger

logger = get_logger("bigrag.vector_store")

# Dedicated thread pool for Milvus I/O so we never block the event loop
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        from bigrag.config import settings

        _executor = ThreadPoolExecutor(
            max_workers=settings.milvus_max_workers, thread_name_prefix="milvus"
        )
    return _executor


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_get_executor(), partial(fn, *args, **kwargs))


# Pymilvus exceptions that indicate a transient connection issue
_TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)


class VectorStore:
    def __init__(self, uri: str = "http://localhost:19530") -> None:
        self.uri = uri
        self.client: MilvusClient | None = None
        self._nprobe: int = 32
        self._max_retries: int = 2

    def configure(self, uri: str, nprobe: int = 32) -> None:
        """Update the URI before connecting. Use instead of calling __init__ directly."""
        self.uri = uri
        self._nprobe = nprobe

    def connect(self) -> None:
        self.client = MilvusClient(uri=self.uri)
        logger.info(f"Connected to Milvus at {self.uri}")

    def reconnect(self) -> None:
        """Reconnect to Milvus if the connection was lost."""
        logger.warning(f"Reconnecting to Milvus at {self.uri}")
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.client = MilvusClient(uri=self.uri)
        logger.info(f"Reconnected to Milvus at {self.uri}")

    async def _run_with_retry(self, fn, *args, **kwargs):
        """Run a Milvus operation with retry and auto-reconnect on transient failures."""
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                return await _run(fn, *args, **kwargs)
            except _TRANSIENT_ERRORS as e:
                last_error = e
                if attempt < self._max_retries:
                    logger.warning(
                        f"Milvus transient error (attempt {attempt + 1}/{self._max_retries + 1}): "
                        f"{e!r}, reconnecting..."
                    )
                    await asyncio.to_thread(self.reconnect)
                else:
                    raise
            except Exception as e:
                # Check if pymilvus wrapped a transient error
                err_str = str(e).lower()
                if any(kw in err_str for kw in ("connect", "timeout", "unavailable", "reset")):
                    last_error = e
                    if attempt < self._max_retries:
                        logger.warning(
                            f"Milvus likely transient error (attempt {attempt + 1}/"
                            f"{self._max_retries + 1}): {e!r}, reconnecting..."
                        )
                        await asyncio.to_thread(self.reconnect)
                    else:
                        raise
                else:
                    raise
        raise last_error  # Should not reach here

    def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("Milvus connection closed")

    def _col(self, name: str) -> str:
        return f"bigrag_{name}"

    @staticmethod
    def _safe_id(value: str) -> str:
        """Escape a string for safe use in Milvus filter expressions."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    async def create_collection(self, name: str, dimension: int) -> None:
        col = self._col(name)

        if await self._run_with_retry(self.client.has_collection, col):
            return

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(
            field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=128
        )
        schema.add_field(field_name="document_id", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=dimension)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 256},
        )

        await self._run_with_retry(
            self.client.create_collection,
            collection_name=col,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"Created Milvus collection: {col} (dim={dimension})")

    async def delete_collection(self, name: str) -> None:
        col = self._col(name)
        if await self._run_with_retry(self.client.has_collection, col):
            await self._run_with_retry(self.client.drop_collection, col)
            logger.info(f"Dropped Milvus collection: {col}")

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
        data = []
        for i in range(len(ids)):
            entry = {
                "id": ids[i],
                "document_id": document_ids[i],
                "chunk_index": chunk_indices[i],
                "text": texts[i],
                "embedding": embeddings[i],
            }
            if metadata and metadata[i]:
                entry.update(metadata[i])
            data.append(entry)

        result = await self._run_with_retry(self.client.insert, collection_name=col, data=data)
        count = result.get("insert_count", len(ids))
        logger.info(f"insert: collection={col} count={count}")
        return count

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[dict]:
        col = self._col(collection)
        if output_fields is None:
            output_fields = ["text", "document_id", "chunk_index"]

        results = await self._run_with_retry(
            self.client.search,
            collection_name=col,
            data=[query_embedding],
            limit=top_k,
            output_fields=output_fields,
            search_params={"metric_type": "COSINE", "params": {"nprobe": self._nprobe}},
            filter=filters,
        )

        hits = []
        if results and len(results) > 0:
            for hit in results[0]:
                hits.append(
                    {
                        "id": hit["id"],
                        "score": hit["distance"],
                        "text": hit["entity"].get("text", ""),
                        "document_id": hit["entity"].get("document_id"),
                        "chunk_index": hit["entity"].get("chunk_index"),
                    }
                )
        logger.info(f"search: collection={col} top_k={top_k} hits={len(hits)} filter={filters}")
        return hits

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
    ) -> list[dict]:
        col = self._col(collection)
        if not self.client.has_collection(col):
            return []
        safe_doc_id = self._safe_id(document_id)
        results = await self._run_with_retry(
            self.client.query,
            collection_name=col,
            filter=f'document_id == "{safe_doc_id}"',
            output_fields=["text", "document_id", "chunk_index"],
            limit=limit,
        )
        chunks = sorted(results, key=lambda r: r.get("chunk_index", 0))
        logger.info(f"get_chunks: collection={col} document_id={document_id} count={len(chunks)}")
        return [
            {"id": r["id"], "text": r.get("text", ""), "chunk_index": r.get("chunk_index", 0)}
            for r in chunks
        ]

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        col = self._col(collection)
        if not self.client.has_collection(col):
            return
        safe_doc_id = self._safe_id(document_id)
        await self._run_with_retry(
            self.client.delete, collection_name=col, filter=f'document_id == "{safe_doc_id}"'
        )
        logger.info(f"delete_by_document: collection={col} document_id={document_id}")

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        col = self._col(collection)
        await self._run_with_retry(self.client.delete, collection_name=col, ids=ids)
        logger.info(f"delete_by_ids: collection={col} count={len(ids)}")

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: str | None = None,
    ) -> list[dict]:
        """Search by text content using keyword matching."""
        col = self._col(collection)

        # Build a filter that matches any of the query terms in the text field
        term_filters = []
        for term in query_terms:
            escaped = term.replace("\\", "\\\\").replace('"', '\\"').replace("%", "\\%")
            term_filters.append(f'text like "%{escaped}%"')

        text_filter = " or ".join(term_filters)
        if filters:
            combined_filter = f"({text_filter}) and ({filters})"
        else:
            combined_filter = text_filter

        try:
            results = await self._run_with_retry(
                self.client.query,
                collection_name=col,
                filter=combined_filter,
                output_fields=["text", "document_id", "chunk_index"],
                limit=top_k * 3,  # Fetch more to allow scoring/ranking
            )
        except _TRANSIENT_ERRORS:
            raise  # Let transient errors propagate for retry at a higher level
        except Exception as e:
            logger.warning(f"text_search query failed: {e!r}, returning empty results")
            return []

        logger.info(f"text_search: collection={col} terms={len(query_terms)} hits={len(results)}")
        return [
            {
                "id": r["id"],
                "text": r.get("text", ""),
                "document_id": r.get("document_id"),
                "chunk_index": r.get("chunk_index"),
            }
            for r in results
        ]

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        col = self._col(collection)
        data = []
        for i in range(len(ids)):
            entry = {
                "id": ids[i],
                "document_id": "",
                "chunk_index": 0,
                "text": texts[i],
                "embedding": embeddings[i],
            }
            if metadata and metadata[i]:
                entry.update(metadata[i])
            data.append(entry)

        result = await self._run_with_retry(self.client.upsert, collection_name=col, data=data)
        count = result.get("upsert_count", len(ids))
        logger.info(f"upsert: collection={col} count={count}")
        return count


vector_store = VectorStore()
