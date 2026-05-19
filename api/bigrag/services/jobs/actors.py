from __future__ import annotations

import asyncio
import uuid

import dramatiq
from dramatiq.asyncio import async_to_sync, get_event_loop_thread

from bigrag.logging import get_logger
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.jobs.broker import (
    BACKUPS_QUEUE,
    CONNECTORS_QUEUE,
    INGESTION_QUEUE,
    MAINTENANCE_QUEUE,
    WEBHOOKS_QUEUE,
    broker,
)
from bigrag.services.jobs.runtime import ensure_worker_runtime, record_worker_heartbeat

logger = get_logger("bigrag.jobs")

GOOGLE_DRIVE_SCHEDULER_KEY = "bigrag:dramatiq:periodic:google_drive"
CLEANUP_SCHEDULER_KEY = "bigrag:dramatiq:periodic:cleanup"
WEBHOOK_OUTBOX_KEY = "bigrag:dramatiq:periodic:webhook_outbox"
GOOGLE_DRIVE_SCHEDULER_SECONDS = 60
CLEANUP_SECONDS = 86400


def _run(async_fn, *args, **kwargs):
    if get_event_loop_thread() is None:
        return asyncio.run(async_fn(*args, **kwargs))
    return async_to_sync(async_fn)(*args, **kwargs)


def enqueue_ingestion_job(job: IngestionJob, *, delay_seconds: int = 0) -> None:
    process_ingestion_job.send_with_options(
        args=(job.serialize().decode(),),
        delay=max(0, int(delay_seconds)) * 1000 if delay_seconds else None,
    )


def enqueue_webhook_outbox(*, delivery_id: str | None = None, delay_seconds: int = 0) -> None:
    process_webhook_outbox.send_with_options(
        kwargs={"delivery_id": delivery_id},
        delay=max(0, int(delay_seconds)) * 1000 if delay_seconds else None,
    )


def enqueue_google_drive_sync(job_id: str, *, delay_seconds: int = 0) -> None:
    run_google_drive_sync.send_with_options(
        args=(job_id,),
        delay=max(0, int(delay_seconds)) * 1000 if delay_seconds else None,
    )


def enqueue_backup_job(job_id: str) -> None:
    run_backup.send(job_id)


def seed_periodic_jobs(enabled_queues: set[str] | None = None) -> None:
    if enabled_queues is None or MAINTENANCE_QUEUE in enabled_queues:
        run_google_drive_scheduler.send()
        run_cleanup.send_with_options(delay=CLEANUP_SECONDS * 1000)
    if enabled_queues is None or WEBHOOKS_QUEUE in enabled_queues:
        process_webhook_outbox.send()


@dramatiq.actor(queue_name=INGESTION_QUEUE, max_retries=0, broker=broker)
def process_ingestion_job(payload: str) -> None:
    _run(_process_ingestion_job, payload)


async def _process_ingestion_job(payload: str) -> None:
    await ensure_worker_runtime()
    from bigrag.services import queue
    from bigrag.services.maintenance import is_active

    job = IngestionJob.deserialize(payload.encode())
    logger.info("ingestion actor received job", job=job.job_id, doc=job.document_id)
    if await is_active():
        enqueue_ingestion_job(job, delay_seconds=10)
        return
    await queue.ingestion_queue.process_leased_job("dramatiq", job)


@dramatiq.actor(queue_name=CONNECTORS_QUEUE, max_retries=0, broker=broker)
def run_google_drive_sync(job_id: str) -> None:
    _run(_run_google_drive_sync, job_id)


async def _run_google_drive_sync(job_id: str) -> None:
    await ensure_worker_runtime()
    from bigrag.services.maintenance import is_active

    if await is_active():
        enqueue_google_drive_sync(job_id, delay_seconds=10)
        return
    from bigrag.services.connectors.google_drive_sync import sync_google_drive_job

    await sync_google_drive_job(job_id)


@dramatiq.actor(queue_name=MAINTENANCE_QUEUE, max_retries=0, broker=broker)
def run_google_drive_scheduler() -> None:
    _run(_run_google_drive_scheduler)


async def _run_google_drive_scheduler() -> None:
    await ensure_worker_runtime()
    try:
        logger.info("google drive scheduler tick starting")
        from bigrag.services.connectors.google_drive_sync import run_due_google_syncs

        await run_due_google_syncs()
        logger.info("google drive scheduler tick complete")
    finally:
        await _schedule_once(
            run_google_drive_scheduler,
            GOOGLE_DRIVE_SCHEDULER_KEY,
            GOOGLE_DRIVE_SCHEDULER_SECONDS,
        )


@dramatiq.actor(queue_name=WEBHOOKS_QUEUE, max_retries=0, broker=broker)
def process_webhook_outbox(delivery_id: str | None = None) -> None:
    _run(_process_webhook_outbox, delivery_id)


async def _process_webhook_outbox(delivery_id: str | None = None) -> None:
    await ensure_worker_runtime()
    from bigrag.services.webhook import WebhookDispatcher

    logger.info("webhook outbox tick starting", delivery_id=delivery_id)
    dispatcher = WebhookDispatcher()
    target_id = uuid.UUID(delivery_id) if delivery_id else None
    processed = await dispatcher.process_due_deliveries(
        delivery_id=target_id,
        limit=1 if target_id else 25,
    )
    logger.info("webhook outbox tick complete", delivery_id=delivery_id, processed=processed)
    if target_id is None:
        await _schedule_once(process_webhook_outbox, WEBHOOK_OUTBOX_KEY, 1 if processed else 5)


@dramatiq.actor(queue_name=BACKUPS_QUEUE, max_retries=0, broker=broker)
def run_backup(job_id: str) -> None:
    _run(_run_backup, job_id)


async def _run_backup(job_id: str) -> None:
    await ensure_worker_runtime()
    from bigrag.services.backup import run_backup_job

    await run_backup_job(job_id)


@dramatiq.actor(queue_name=MAINTENANCE_QUEUE, max_retries=0, broker=broker)
def run_cleanup() -> None:
    _run(_run_cleanup)


async def _run_cleanup() -> None:
    await ensure_worker_runtime()
    try:
        from bigrag.services.cleanup import cleanup_old_data_once

        await cleanup_old_data_once()
    finally:
        await _schedule_once(run_cleanup, CLEANUP_SCHEDULER_KEY, CLEANUP_SECONDS)


async def _schedule_once(actor, key: str, delay_seconds: int) -> None:
    from bigrag.services.queue import ingestion_queue

    await record_worker_heartbeat()
    redis = ingestion_queue.redis
    if redis is None:
        actor.send_with_options(delay=delay_seconds * 1000)
        return
    scheduled = await redis.set(key, b"1", ex=max(1, delay_seconds), nx=True)
    if scheduled:
        actor.send_with_options(delay=delay_seconds * 1000)
