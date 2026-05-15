from __future__ import annotations

import asyncio
import inspect
import uuid

from bigrag import main
from bigrag.services import queue
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.jobs import actors


def run(coro):
    return asyncio.run(coro)


def job_payload() -> str:
    return (
        IngestionJob(
            document_id="11111111-1111-1111-1111-111111111111",
            file_path="docs/a.txt",
            collection_name="docs",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_dimension=2,
            chunk_size=400,
            chunk_overlap=40,
            job_id="job",
        )
        .serialize()
        .decode()
    )


def test_ingestion_actor_delays_when_maintenance_is_active(monkeypatch) -> None:
    async def ensure_runtime():
        return None

    async def is_active():
        return True

    delayed = []

    def enqueue(job, *, delay_seconds=0):
        delayed.append((job.job_id, delay_seconds))

    monkeypatch.setattr(actors, "ensure_worker_runtime", ensure_runtime)
    monkeypatch.setattr("bigrag.services.maintenance.is_active", is_active)
    monkeypatch.setattr(actors, "enqueue_ingestion_job", enqueue)

    run(actors._process_ingestion_job(job_payload()))

    assert delayed == [("job", 10)]


def test_ingestion_actor_processes_leased_job(monkeypatch) -> None:
    async def ensure_runtime():
        return None

    async def is_active():
        return False

    processed = []

    async def process(worker_id, job):
        processed.append((worker_id, job.job_id))

    monkeypatch.setattr(actors, "ensure_worker_runtime", ensure_runtime)
    monkeypatch.setattr("bigrag.services.maintenance.is_active", is_active)
    monkeypatch.setattr(queue.ingestion_queue, "process_leased_job", process)

    run(actors._process_ingestion_job(job_payload()))

    assert processed == [("dramatiq", "job")]


def test_webhook_outbox_actor_claims_specific_delivery(monkeypatch) -> None:
    delivery_id = uuid.uuid4()
    processed = []

    async def ensure_runtime():
        return None

    class Dispatcher:
        async def process_due_deliveries(self, *, delivery_id=None, limit=25):
            processed.append((delivery_id, limit))
            return 1

    monkeypatch.setattr(actors, "ensure_worker_runtime", ensure_runtime)
    monkeypatch.setattr("bigrag.services.webhook.WebhookDispatcher", Dispatcher)

    run(actors._process_webhook_outbox(str(delivery_id)))

    assert processed == [(delivery_id, 1)]


def test_backup_and_cleanup_actors_call_domain_services(monkeypatch) -> None:
    calls = []

    async def ensure_runtime():
        return None

    async def backup(job_id):
        calls.append(("backup", job_id))

    async def cleanup_once():
        calls.append(("cleanup", None))

    async def schedule_once(actor, key, delay_seconds):
        calls.append(("schedule", key, delay_seconds))

    monkeypatch.setattr(actors, "ensure_worker_runtime", ensure_runtime)
    monkeypatch.setattr("bigrag.services.backup.run_backup_job", backup)
    monkeypatch.setattr("bigrag.services.cleanup.cleanup_old_data_once", cleanup_once)
    monkeypatch.setattr(actors, "_schedule_once", schedule_once)

    run(actors._run_backup("backup-id"))
    run(actors._run_cleanup())

    assert calls == [
        ("backup", "backup-id"),
        ("cleanup", None),
        ("schedule", actors.CLEANUP_SCHEDULER_KEY, actors.CLEANUP_SECONDS),
    ]


def test_api_lifespan_does_not_start_background_job_loops() -> None:
    source = inspect.getsource(main.lifespan)

    assert "WebhookDispatcher" not in source
    assert "google_drive_scheduler" not in source
    assert "cleanup_old_data" not in source
    assert ".start(vector_store" not in source


def test_periodic_seed_respects_queue_filter(monkeypatch) -> None:
    calls = []

    class Actor:
        def __init__(self, name) -> None:
            self.name = name

        def send(self) -> None:
            calls.append((self.name, "send"))

        def send_with_options(self, **kwargs) -> None:
            calls.append((self.name, kwargs["delay"]))

    monkeypatch.setattr(actors, "run_google_drive_scheduler", Actor("scheduler"))
    monkeypatch.setattr(actors, "process_webhook_outbox", Actor("webhooks"))
    monkeypatch.setattr(actors, "run_cleanup", Actor("cleanup"))

    actors.seed_periodic_jobs({"webhooks"})

    assert calls == [("webhooks", "send")]
