from __future__ import annotations

from typing import Any, Protocol

import redis.asyncio as aioredis

from bigrag.services.document_elements import ParsedDocument
from bigrag.services.event_bus import IngestionEvent
from bigrag.services.ingestion_job import IngestionJob


class IngestionQueueRuntime(Protocol):
    @property
    def redis(self) -> aioredis.Redis | None: ...

    @property
    def vector_store(self) -> Any: ...

    def publish_progress(
        self,
        doc_id: str,
        step: str,
        status: str,
        msg: str,
        progress: float = 0.0,
        collection_name: str = "",
        **detail,
    ) -> IngestionEvent: ...

    async def ensure_job_current(self, job: IngestionJob) -> None: ...

    async def convert_document(self, job: IngestionJob, prefix: str) -> ParsedDocument: ...

    async def chunk_and_embed(
        self,
        job: IngestionJob,
        parsed: ParsedDocument,
        prefix: str,
    ) -> tuple[int, int]: ...

    async def release_job(self) -> None: ...

    async def enqueue_retry(self, job: IngestionJob, *, delay_seconds: float = 0) -> None: ...


def require_queue_redis(runtime: IngestionQueueRuntime) -> aioredis.Redis:
    redis = runtime.redis
    if redis is None:
        raise RuntimeError("ingestion queue is not connected")
    return redis
