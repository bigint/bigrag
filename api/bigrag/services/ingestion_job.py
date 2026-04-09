from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import orjson


@dataclass
class IngestionJob:
    document_id: str
    file_path: str
    collection_name: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_api_key: str | None
    chunk_size: int
    chunk_overlap: int
    attempt: int = 0
    max_attempts: int = 3
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def serialize(self) -> bytes:
        return orjson.dumps(
            {
                "document_id": self.document_id,
                "file_path": self.file_path,
                "collection_name": self.collection_name,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
                "embedding_api_key": self.embedding_api_key,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "attempt": self.attempt,
                "max_attempts": self.max_attempts,
                "job_id": self.job_id,
            }
        )

    @classmethod
    def deserialize(cls, data: bytes) -> IngestionJob:
        return cls(**orjson.loads(data))


def create_ingestion_job(
    *,
    document_id: str,
    file_path: str,
    collection_name: str,
    collection: dict,
    fallback_api_key: str | None,
) -> IngestionJob:
    """Factory to create an IngestionJob from a collection dict."""
    return IngestionJob(
        document_id=document_id,
        file_path=file_path,
        collection_name=collection_name,
        embedding_provider=collection["embedding_provider"],
        embedding_model=collection["embedding_model"],
        embedding_dimension=collection["dimension"],
        embedding_api_key=collection.get("embedding_api_key") or fallback_api_key,
        chunk_size=collection["chunk_size"],
        chunk_overlap=collection["chunk_overlap"],
    )
