from __future__ import annotations

import logging
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema

logger = logging.getLogger("bigrag.vector_store")


class VectorStore:
    def __init__(self, uri: str = "http://localhost:19530") -> None:
        self.uri = uri
        self.client: MilvusClient | None = None

    def connect(self) -> None:
        self.client = MilvusClient(uri=self.uri)
        logger.info(f"Connected to Milvus at {self.uri}")

    def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("Milvus connection closed")

    def _collection_name(self, name: str) -> str:
        return f"bigrag_{name}"

    def create_collection(self, name: str, dimension: int) -> None:
        col_name = self._collection_name(name)

        if self.client.has_collection(col_name):
            logger.info(f"Collection {col_name} already exists")
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

        self.client.create_collection(
            collection_name=col_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info(f"Created Milvus collection: {col_name} (dim={dimension})")

    def delete_collection(self, name: str) -> None:
        col_name = self._collection_name(name)
        if self.client.has_collection(col_name):
            self.client.drop_collection(col_name)
            logger.info(f"Dropped Milvus collection: {col_name}")

    def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int:
        col_name = self._collection_name(collection)

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

        result = self.client.insert(collection_name=col_name, data=data)
        count = result.get("insert_count", len(ids))
        logger.info(f"Inserted {count} vectors into {col_name}")
        return count

    def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[dict]:
        col_name = self._collection_name(collection)

        if output_fields is None:
            output_fields = ["text", "document_id", "chunk_index"]

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 32}}

        results = self.client.search(
            collection_name=col_name,
            data=[query_embedding],
            limit=top_k,
            output_fields=output_fields,
            search_params=search_params,
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
        return hits

    def delete_by_document(self, collection: str, document_id: str) -> None:
        col_name = self._collection_name(collection)
        self.client.delete(
            collection_name=col_name,
            filter=f'document_id == "{document_id}"',
        )
        logger.info(f"Deleted vectors for document {document_id} from {col_name}")

    def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        col_name = self._collection_name(collection)
        self.client.delete(collection_name=col_name, ids=ids)
        logger.info(f"Deleted {len(ids)} vectors from {col_name}")

    def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        col_name = self._collection_name(collection)

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

        result = self.client.upsert(collection_name=col_name, data=data)
        count = result.get("upsert_count", len(ids))
        logger.info(f"Upserted {count} vectors into {col_name}")
        return count

    def get_collection_stats(self, name: str) -> dict | None:
        col_name = self._collection_name(name)
        if not self.client.has_collection(col_name):
            return None
        stats = self.client.get_collection_stats(col_name)
        return stats


vector_store = VectorStore()
