from __future__ import annotations

import asyncio
import importlib

from rag_computer.services import queue
from rag_computer.services.ingestion_job import IngestionJob


class FakeRedis:
    def __init__(self) -> None:
        self.hashes = {}
        self.lists = {}
        self.deleted = []
        self.closed = False

    async def ping(self) -> None:
        return None

    async def aclose(self) -> None:
        self.closed = True

    async def hincrby(self, key, field, amount):
        self.hashes[(key, field)] = self.hashes.get((key, field), 0) + amount

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, start, end):
        self.lists[key] = self.lists.get(key, [])[start : end + 1]

    async def delete(self, key):
        self.deleted.append(key)


class FakeSession:
    def __init__(self) -> None:
        self.executed = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)

    async def commit(self):
        self.commits += 1


class FakeEventBus:
    def __init__(self) -> None:
        self.published = []
        self.completed = []

    def publish(self, event):
        self.published.append(event)

    def complete(self, document_id):
        self.completed.append(document_id)


def job(**overrides) -> IngestionJob:
    values = {
        "document_id": "11111111-1111-1111-1111-111111111111",
        "file_path": "docs/a.txt",
        "collection_name": "docs",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimension": 2,
        "chunk_size": 400,
        "chunk_overlap": 40,
        "job_id": "job",
    }
    values.update(overrides)
    return IngestionJob(**values)


def configure_queue_process(monkeypatch):
    sessions = []
    events = FakeEventBus()

    def outer():
        def inner():
            session = FakeSession()
            sessions.append(session)
            return session

        return inner

    async def invalidate(collection_name):
        events.completed.append(f"invalidate:{collection_name}")

    monkeypatch.setattr(importlib.import_module("rag_computer.db.engine"), "session_factory", outer)
    monkeypatch.setattr(
        "rag_computer.services.retrieval.invalidate_collection_query_cache",
        invalidate,
    )
    monkeypatch.setattr(queue, "event_bus", events)
    return sessions, events


def test_queue_connect_start_resize_stop_and_no_redis_paths(monkeypatch) -> None:
    async def run() -> None:
        redis = FakeRedis()
        created_workers = []

        async def recover(redis_arg):
            assert redis_arg is redis
            return 1

        async def idle_worker(worker_id):
            created_workers.append(worker_id)

        def from_url(redis_url, **kwargs):
            assert redis_url == "redis://localhost"
            assert kwargs["decode_responses"] is False
            return redis

        monkeypatch.setattr(queue.aioredis, "from_url", from_url)
        monkeypatch.setattr(queue.queue_state, "recover_stuck_jobs", recover)

        ingestion_queue = queue.IngestionQueue(num_workers=1)
        monkeypatch.setattr(ingestion_queue, "_worker", idle_worker)

        assert await ingestion_queue.flush_collection("docs") == 0
        await ingestion_queue.cancel_documents(["doc"])
        assert await ingestion_queue.stats == {"queued": 0, "completed": 0, "failed": 0}

        await ingestion_queue.connect("redis://localhost")
        await ingestion_queue.start(vector_store=object())
        await asyncio.sleep(0)
        await ingestion_queue.resize_workers(3)
        await asyncio.sleep(0)
        await ingestion_queue.resize_workers(1)
        await ingestion_queue.stop()

        assert created_workers == [0, 1, 2]
        assert redis.closed is True

    async def stats(redis):
        return {"queued": 0, "completed": 0, "failed": 0}

    monkeypatch.setattr(queue.queue_state, "queue_stats", stats)
    asyncio.run(run())


def test_queue_enqueue_flush_cancel_and_full_queue(monkeypatch) -> None:
    async def run() -> None:
        redis = FakeRedis()
        ingestion_queue = queue.IngestionQueue()
        ingestion_queue._redis = redis
        enqueued = []

        async def ensure_writes_allowed():
            return None

        async def get_value(key):
            assert key == "queue_max_depth"
            return 10

        async def collection_epoch(redis_arg, collection_name):
            return 7

        async def document_epoch(redis_arg, document_id):
            return 11

        async def enqueue_job(redis_arg, job_arg, max_depth):
            enqueued.append((job_arg, max_depth))
            return -1 if job_arg.job_id == "full" else 2

        async def flush_jobs(redis_arg, collection_name):
            return 3

        async def cancel_collection(redis_arg, collection_name):
            return 4

        async def cancel_documents(redis_arg, document_ids):
            enqueued.append(("cancel", document_ids))

        monkeypatch.setattr(
            "rag_computer.services.maintenance.ensure_writes_allowed",
            ensure_writes_allowed,
        )
        monkeypatch.setattr("rag_computer.services.runtime_settings.get_value", get_value)
        monkeypatch.setattr(queue.queue_state, "collection_epoch", collection_epoch)
        monkeypatch.setattr(queue.queue_state, "document_epoch", document_epoch)
        monkeypatch.setattr(queue.queue_state, "enqueue_job", enqueue_job)
        monkeypatch.setattr(queue.queue_state, "flush_collection_jobs", flush_jobs)
        monkeypatch.setattr(queue.queue_state, "cancel_collection_jobs", cancel_collection)
        monkeypatch.setattr(queue.queue_state, "cancel_document_jobs", cancel_documents)

        normal = job()
        await ingestion_queue.enqueue(normal)
        assert normal.collection_epoch == 7
        assert normal.document_epoch == 11
        assert await ingestion_queue.flush_collection("docs") == 3
        assert await ingestion_queue.cancel_collection("docs") == 4
        await ingestion_queue.cancel_documents(["doc"])

        try:
            await ingestion_queue.enqueue(job(job_id="full"))
        except ValueError as exc:
            assert "queue is full" in str(exc)
        else:
            raise AssertionError("expected full queue")

    asyncio.run(run())


def test_queue_process_job_success_retry_cancel_and_permanent_failure(monkeypatch) -> None:
    async def run() -> None:
        sessions, events = configure_queue_process(monkeypatch)
        redis = FakeRedis()
        ingestion_queue = queue.IngestionQueue()
        ingestion_queue._redis = redis
        ingestion_queue._vector_store = object()
        checks = []
        enqueued = []
        cleanups = []

        async def ensure_current(job_arg):
            checks.append(job_arg.job_id)
            if job_arg.job_id == "cancel":
                raise queue.IngestionCancelledError("cancelled")

        async def convert(job_arg, prefix):
            if job_arg.job_id == "convert-fail":
                raise RuntimeError("convert failed")
            return "hello world"

        async def chunk(job_arg, text, prefix):
            if job_arg.job_id in {"retry", "dead"}:
                raise RuntimeError("embed failed")
            return (2, 2)

        async def enqueue_again(job_arg):
            enqueued.append(job_arg.job_id)

        async def cleanup(vector_store, collection_name, document_id, **kwargs):
            cleanups.append((collection_name, document_id, kwargs["log_message"]))

        monkeypatch.setattr(ingestion_queue, "_ensure_job_current", ensure_current)
        monkeypatch.setattr(ingestion_queue, "_convert_document", convert)
        monkeypatch.setattr(ingestion_queue, "_chunk_and_embed", chunk)
        monkeypatch.setattr(ingestion_queue, "enqueue", enqueue_again)
        monkeypatch.setattr(queue, "_delete_document_vectors_after_failure", cleanup)

        await ingestion_queue._process_job(0, job(job_id="success"))
        await ingestion_queue._process_job(0, job(job_id="retry", max_attempts=2))
        await ingestion_queue._process_job(0, job(job_id="cancel"))
        await ingestion_queue._process_job(0, job(job_id="dead", max_attempts=1))

        assert enqueued == ["retry"]
        assert len(cleanups) == 2
        assert redis.hashes[(queue.STATS_KEY, "completed")] == 1
        assert redis.hashes[(queue.STATS_KEY, "failed")] == 1
        assert queue.DEAD_LETTER_KEY in redis.lists
        assert "11111111-1111-1111-1111-111111111111" in events.completed
        assert "invalidate:docs" in events.completed
        assert len(sessions) >= 5
        assert checks[:2] == ["success", "success"]

    asyncio.run(run())
