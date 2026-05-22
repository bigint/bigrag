from __future__ import annotations

import asyncio
import json
import uuid

import dramatiq
from dramatiq.asyncio import async_to_sync, get_event_loop_thread

from bigrag.logging import current_worker_label, get_logger
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


def enqueue_multimodal_enrichment(
    document_id: str,
    *,
    delay_seconds: int = 0,
    attempt: int = 0,
) -> None:
    process_multimodal_enrichment.send_with_options(
        args=(document_id, attempt),
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
        _schedule_sync(
            run_google_drive_scheduler,
            GOOGLE_DRIVE_SCHEDULER_KEY,
            GOOGLE_DRIVE_SCHEDULER_SECONDS,
            skip_if_delayed_exists=True,
        )
        _schedule_sync(
            run_cleanup,
            CLEANUP_SCHEDULER_KEY,
            CLEANUP_SECONDS,
            skip_if_delayed_exists=True,
        )
    if enabled_queues is None or WEBHOOKS_QUEUE in enabled_queues:
        _schedule_sync(
            process_webhook_outbox,
            WEBHOOK_OUTBOX_KEY,
            1,
            skip_if_delayed_exists=True,
        )


@dramatiq.actor(queue_name=INGESTION_QUEUE, max_retries=0, broker=broker)
def process_ingestion_job(payload: str) -> None:
    _run(_process_ingestion_job, payload)


async def _process_ingestion_job(payload: str) -> None:
    await ensure_worker_runtime()
    from bigrag.services import queue
    from bigrag.services.maintenance import is_active

    job = IngestionJob.deserialize(payload.encode())
    logger.debug("ingestion actor received job", job=job.job_id, doc=job.document_id)
    if await is_active():
        enqueue_ingestion_job(job, delay_seconds=10)
        return
    await queue.ingestion_queue.process_leased_job(current_worker_label(), job)


@dramatiq.actor(queue_name=INGESTION_QUEUE, max_retries=0, broker=broker)
def process_multimodal_enrichment(document_id: str, attempt: int = 0) -> None:
    _run(_process_multimodal_enrichment, document_id, attempt)


async def _process_multimodal_enrichment(document_id: str, attempt: int = 0) -> None:
    await ensure_worker_runtime()
    from bigrag.services.multimodal_enrichment import (
        enrich_document_elements,
        mark_document_enrichment_failed,
    )

    try:
        enriched = await enrich_document_elements(document_id)
        logger.info(f"multimodal enrichment complete | {enriched} elements")
    except Exception as exc:
        if attempt < 3:
            delay = min(2 ** (attempt + 1), 30)
            logger.warning(
                "multimodal enrichment retrying",
                doc=document_id,
                attempt=attempt,
                delay=delay,
                error=repr(exc),
            )
            enqueue_multimodal_enrichment(
                document_id,
                delay_seconds=delay,
                attempt=attempt + 1,
            )
            return
        await mark_document_enrichment_failed(document_id, str(exc))
        logger.error("multimodal enrichment failed", doc=document_id, error=repr(exc))


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
    try:
        _run(_run_google_drive_scheduler)
    finally:
        _schedule_sync(
            run_google_drive_scheduler,
            GOOGLE_DRIVE_SCHEDULER_KEY,
            GOOGLE_DRIVE_SCHEDULER_SECONDS,
        )


async def _run_google_drive_scheduler() -> None:
    await ensure_worker_runtime()
    logger.info("google drive scheduler tick starting")
    from bigrag.services.connectors.google_drive_sync import run_due_google_syncs

    await run_due_google_syncs()
    logger.info("google drive scheduler tick complete")


@dramatiq.actor(queue_name=WEBHOOKS_QUEUE, max_retries=0, broker=broker)
def process_webhook_outbox(delivery_id: str | None = None) -> None:
    delay_seconds = _run(_process_webhook_outbox, delivery_id)
    if delay_seconds is not None:
        process_webhook_outbox.send_with_options(delay=delay_seconds * 1000)


async def _process_webhook_outbox(delivery_id: str | None = None) -> int | None:
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
        delay_seconds = 1 if processed else 5
        if await _claim_schedule_once(WEBHOOK_OUTBOX_KEY, delay_seconds):
            return delay_seconds
    return None


@dramatiq.actor(queue_name=BACKUPS_QUEUE, max_retries=0, broker=broker)
def run_backup(job_id: str) -> None:
    _run(_run_backup, job_id)


async def _run_backup(job_id: str) -> None:
    await ensure_worker_runtime()
    from bigrag.services.backup import run_backup_job

    await run_backup_job(job_id)


@dramatiq.actor(queue_name=MAINTENANCE_QUEUE, max_retries=0, broker=broker)
def run_cleanup() -> None:
    try:
        _run(_run_cleanup)
    finally:
        _schedule_sync(run_cleanup, CLEANUP_SCHEDULER_KEY, CLEANUP_SECONDS)


async def _run_cleanup() -> None:
    await ensure_worker_runtime()
    from bigrag.services.cleanup import cleanup_old_data_once

    await cleanup_old_data_once()


def _schedule_sync(
    actor,
    key: str,
    delay_seconds: int,
    *,
    skip_if_delayed_exists: bool = False,
) -> None:
    if _run(_claim_schedule_once, key, delay_seconds, actor if skip_if_delayed_exists else None):
        actor.send_with_options(delay=delay_seconds * 1000)


async def _claim_schedule_once(key: str, delay_seconds: int, actor=None) -> bool:
    from bigrag.services.queue import ingestion_queue

    await record_worker_heartbeat()
    redis = ingestion_queue.redis
    if redis is None:
        return True
    if actor is not None and await _delayed_actor_exists(redis, actor):
        return False
    scheduled = await redis.set(key, b"1", ex=max(1, delay_seconds), nx=True)
    return bool(scheduled)


async def _delayed_actor_exists(redis, actor) -> bool:
    from bigrag.services.jobs.broker import delayed_messages_key

    raw_messages = await redis.hvals(delayed_messages_key(actor.queue_name))
    for raw_message in raw_messages:
        try:
            text = raw_message.decode() if isinstance(raw_message, bytes) else raw_message
            message = json.loads(text)
        except (TypeError, ValueError, UnicodeDecodeError):
            continue
        if message.get("actor_name") == actor.actor_name:
            return True
    return False
