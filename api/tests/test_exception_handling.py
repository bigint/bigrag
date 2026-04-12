"""Tests that formerly-silent failures now log and surface via status."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue import IngestionQueue


def _job_bytes(collection_name: str) -> bytes:
    return IngestionJob(
        document_id="doc-1",
        file_path="test_col/doc-1.pdf",
        collection_name=collection_name,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        embedding_api_key="sk-test",
        chunk_size=512,
        chunk_overlap=50,
    ).serialize()


@pytest.mark.asyncio
async def test_flush_collection_logs_malformed_job(capfd):
    """A malformed payload must be logged at WARNING and skipped —
    not silently continued past.

    Uses capfd because structlog writes through its own stream handler,
    which bypasses pytest's caplog fixture.
    """
    from bigrag.logging import configure_logging

    configure_logging(log_level="info", log_format="text")

    q = IngestionQueue()
    q._redis = AsyncMock()
    q._redis.lrange = AsyncMock(
        return_value=[_job_bytes("my-col"), b"not-valid-json", _job_bytes("other")]
    )
    q._redis.lrem = AsyncMock()

    removed = await q.flush_collection("my-col")

    assert removed == 1
    # lrem called exactly once for the matching valid job
    assert q._redis.lrem.await_count == 1
    # The malformed payload was logged, not silently ignored
    captured = capfd.readouterr()
    output = captured.out + captured.err
    assert "malformed job payload" in output.lower(), (
        f"Expected 'malformed job payload' in log output. Got:\n{output}"
    )


@pytest.mark.asyncio
async def test_flush_collection_handles_empty_queue():
    q = IngestionQueue()
    q._redis = AsyncMock()
    q._redis.lrange = AsyncMock(return_value=[])
    q._redis.lrem = AsyncMock()

    removed = await q.flush_collection("my-col")
    assert removed == 0
    assert q._redis.lrem.await_count == 0
