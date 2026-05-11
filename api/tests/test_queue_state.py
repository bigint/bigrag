from __future__ import annotations

import asyncio

from bigrag.services import queue, queue_state
from bigrag.services.ingestion_job import IngestionJob


class FakePipeline:
    def __init__(self, redis) -> None:
        self.redis = redis
        self.keys = []

    def incr(self, key: str) -> None:
        self.keys.append(key)

    async def execute(self) -> None:
        for key in self.keys:
            await self.redis.incr(key)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.lists = {
            queue_state.QUEUE_KEY: [],
            queue_state.PROCESSING_KEY: [],
        }
        self.hashes = {queue_state.STATS_KEY: {}}
        self.eval_calls = []

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1

    async def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]

    async def lrem(self, key, count, raw):
        self.lists[key] = [item for item in self.lists.get(key, []) if item != raw]

    async def lpush(self, key, raw):
        self.lists.setdefault(key, []).insert(0, raw)

    async def exists(self, key):
        return key in self.values

    async def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value

    async def hgetall(self, key):
        return self.hashes.get(key, {})

    async def llen(self, key):
        return len(self.lists.get(key, []))

    async def eval(self, script, keys, *args):
        self.eval_calls.append((script, keys, args))
        if script == queue_state.ENQUEUE_LUA:
            _, _, raw, max_depth = args
            if len(self.lists[queue_state.QUEUE_KEY]) >= int(max_depth):
                return -1
            self.lists[queue_state.QUEUE_KEY].insert(0, raw)
            self.hashes[queue_state.STATS_KEY][b"queued"] = (
                self.hashes[queue_state.STATS_KEY].get(b"queued", 0) + 1
            )
            return len(self.lists[queue_state.QUEUE_KEY])
        if script == queue_state.FLUSH_LUA:
            collection_name = args[1]
            kept = []
            removed = 0
            for raw in self.lists[queue_state.QUEUE_KEY]:
                job = IngestionJob.deserialize(raw)
                if job.collection_name == collection_name:
                    removed += 1
                else:
                    kept.append(raw)
            self.lists[queue_state.QUEUE_KEY] = kept
            return removed
        raise AssertionError(script)

    def pipeline(self, transaction=False):
        assert transaction is False
        return FakePipeline(self)


def _job(**overrides) -> IngestionJob:
    values = {
        "document_id": "11111111-1111-1111-1111-111111111111",
        "file_path": "docs/a.txt",
        "collection_name": "docs",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 1536,
        "chunk_size": 400,
        "chunk_overlap": 40,
        "job_id": "job",
    }
    values.update(overrides)
    return IngestionJob(**values)


def test_queue_module_preserves_public_compatibility_exports() -> None:
    assert queue.QUEUE_KEY == queue_state.QUEUE_KEY
    assert queue.PROCESSING_KEY == queue_state.PROCESSING_KEY
    assert queue.DEAD_LETTER_KEY == queue_state.DEAD_LETTER_KEY
    assert queue._lease_key("abc") == "bigrag:ingestion:lease:abc"
    assert queue._collection_epoch_key("docs") == "bigrag:ingestion:collection_epoch:docs"
    assert queue._document_epoch_key("doc") == "bigrag:ingestion:document_epoch:doc"
    assert isinstance(queue.ingestion_queue, queue.IngestionQueue)


def test_queue_state_recovers_unleased_processing_jobs_and_drops_malformed_payloads() -> None:
    async def run() -> None:
        redis = FakeRedis()
        raw = _job(job_id="recover").serialize()
        leased = _job(job_id="leased").serialize()
        redis.lists[queue_state.PROCESSING_KEY] = [raw, b"{", leased]
        redis.values[queue_state.lease_key("leased")] = b"1"

        recovered = await queue_state.recover_stuck_jobs(redis)

        assert recovered == 1
        assert redis.lists[queue_state.QUEUE_KEY] == [raw]
        assert redis.lists[queue_state.PROCESSING_KEY] == [leased]
        assert redis.hashes[queue_state.STATS_KEY]["processing"] == 0

    asyncio.run(run())


def test_queue_state_epochs_and_cancellation_markers() -> None:
    async def run() -> None:
        redis = FakeRedis()
        job = _job(collection_epoch=0, document_epoch=0)
        await queue_state.ensure_job_current(redis, job)

        await queue_state.cancel_document_jobs(redis, [job.document_id])

        try:
            await queue_state.ensure_job_current(redis, job)
        except queue_state.IngestionCancelledError as exc:
            assert "document" in str(exc)
        else:
            raise AssertionError("expected cancellation")

    asyncio.run(run())


def test_queue_state_enqueue_flush_and_stats_shape() -> None:
    async def run() -> None:
        redis = FakeRedis()
        docs_job = _job(collection_name="docs").serialize()
        other_job = _job(
            collection_name="other", document_id="22222222-2222-2222-2222-222222222222"
        )

        assert await queue_state.enqueue_job(redis, IngestionJob.deserialize(docs_job), 5) == 1
        assert await queue_state.enqueue_job(redis, other_job, 5) == 2
        assert await queue_state.flush_collection_jobs(redis, "docs") == 1

        stats = await queue_state.queue_stats(redis)

        assert stats == {
            "queued": 2,
            "completed": 0,
            "failed": 0,
            "pending": 1,
            "processing": 0,
        }

    asyncio.run(run())
