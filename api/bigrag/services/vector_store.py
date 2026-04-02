"""Async wrapper around pymilvus MilvusClient. All blocking calls run in a thread pool."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from pymilvus import MilvusClient, DataType

logger = logging.getLogger("bigrag.vector_store")

# Dedicated thread pool for Milvus I/O so we never block the event loop
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="milvus")


async def _run(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(fn, *args, **kwargs))


class VectorStore:
    def __init__(self, uri: str = "http://localhost:19530") -> None:
        self.uri = uri
        self.client: MilvusClient | None = None

    def configure(self, uri: str) -> None:
        """Update the URI before connecting. Use instead of calling __init__ directly."""
        self.uri = uri

    def connect(self) -> None:
        self.client = MilvusClient(uri=self.uri)
        logger.info(f"Connected to Milvus at {self.uri}")

    def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("Milvus connection closed")

    def _col(self, name: str) -> str:
        return f"bigrag_{name}"

    async def create_collection(self, name: str, dimension: int) -> None:
        col = self._col(name)

        if await _run(self.client.has_collection, col):
            return

        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=128)
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

        await _run(
            self.client.create_collection,
            collection_name=col, schema=schema, index_params=index_params,
        )
        logger.info(f"Created Milvus collection: {col} (dim={dimension})")

    async def delete_collection(self, name: str) -> None:
        col = self._col(name)
        if await _run(self.client.has_collection, col):
            await _run(self.client.drop_collection, col)
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

        result = await _run(self.client.insert, collection_name=col, data=data)
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

        results = await _run(
            self.client.search,
            collection_name=col,
            data=[query_embedding],
            limit=top_k,
            output_fields=output_fields,
            search_params={"metric_type": "COSINE", "params": {"nprobe": 32}},
            filter=filters,
        )

        hits = []
        if results and len(results) > 0:
            for hit in results[0]:
                hits.append({
                    "id": hit["id"],
                    "score": hit["distance"],
                    "text": hit["entity"].get("text", ""),
                    "document_id": hit["entity"].get("document_id"),
                    "chunk_index": hit["entity"].get("chunk_index"),
                })
        logger.info(f"search: collection={col} top_k={top_k} hits={len(hits)} filter={filters}")
        return hits

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        col = self._col(collection)
        await _run(self.client.delete, collection_name=col, filter=f'document_id == "{document_id}"')
        logger.info(f"delete_by_document: collection={col} document_id={document_id}")

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        col = self._col(collection)
        await _run(self.client.delete, collection_name=col, ids=ids)
        logger.info(f"delete_by_ids: collection={col} count={len(ids)}")

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
                "id": ids[i], "document_id": "", "chunk_index": 0,
                "text": texts[i], "embedding": embeddings[i],
            }
            if metadata and metadata[i]:
                entry.update(metadata[i])
            data.append(entry)

        result = await _run(self.client.upsert, collection_name=col, data=data)
        count = result.get("upsert_count", len(ids))
        logger.info(f"upsert: collection={col} count={count}")
        return count


vector_store = VectorStore()
