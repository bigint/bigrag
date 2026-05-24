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
    chunk_size: int
    chunk_overlap: int
    chunk_strategy: str = "paragraph"
    tenant_field: str | None = None
    embedding_base_url: str | None = None
    multimodal_enabled: bool = False
    multimodal_enrichment_enabled: bool = False
    collection_epoch: int = 0
    document_epoch: int = 0
    attempt: int = 0
    max_attempts: int = 3
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    @property
    def should_enrich_multimodal(self) -> bool:
        return self.multimodal_enrichment_enabled and self.embedding_provider == "openai"

    def serialize(self) -> bytes:
        return orjson.dumps(
            {
                "document_id": self.document_id,
                "file_path": self.file_path,
                "collection_name": self.collection_name,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
                "embedding_base_url": self.embedding_base_url,
                "multimodal_enabled": self.multimodal_enabled,
                "multimodal_enrichment_enabled": self.multimodal_enrichment_enabled,
                "collection_epoch": self.collection_epoch,
                "document_epoch": self.document_epoch,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "chunk_strategy": self.chunk_strategy,
                "tenant_field": self.tenant_field,
                "attempt": self.attempt,
                "max_attempts": self.max_attempts,
                "job_id": self.job_id,
            }
        )

    @classmethod
    def deserialize(cls, data: bytes) -> IngestionJob:
        payload = orjson.loads(data)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        clean = {k: v for k, v in payload.items() if k in known}
        return cls(**clean)


def create_ingestion_job(
    *,
    document_id: str,
    file_path: str,
    collection_name: str,
    collection: dict,
) -> IngestionJob:
    return IngestionJob(
        document_id=document_id,
        file_path=file_path,
        collection_name=collection_name,
        embedding_provider=collection["embedding_provider"],
        embedding_model=collection["embedding_model"],
        embedding_dimension=collection["dimension"],
        embedding_base_url=collection.get("embedding_base_url"),
        chunk_size=collection["chunk_size"],
        chunk_overlap=collection["chunk_overlap"],
        chunk_strategy=collection.get("chunk_strategy") or "paragraph",
        tenant_field=collection.get("tenant_field"),
        multimodal_enabled=bool(collection.get("multimodal_enabled")),
        multimodal_enrichment_enabled=bool(collection.get("multimodal_enrichment_enabled")),
    )
