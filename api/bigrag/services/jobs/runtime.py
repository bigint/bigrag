from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from bigrag import __version__
from bigrag import config as config_module
from bigrag import db as db_module
from bigrag.db.bootstrap import run_migrations
from bigrag.logging import configure_logging, get_logger
from bigrag.services import crypto, redis_cache, runtime_settings
from bigrag.services.conversion import get_conversion_executor
from bigrag.services.event_bus import event_bus
from bigrag.services.jobs.broker import (
    BACKUPS_QUEUE,
    CONNECTORS_QUEUE,
    INGESTION_QUEUE,
    MAINTENANCE_QUEUE,
    WEBHOOKS_QUEUE,
    WORKER_HEARTBEAT_KEY,
    worker_heartbeat_key,
)
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import init_storage_from_runtime
from bigrag.services.vector_store import vector_store
from bigrag.startup_guard import check_production_safety

logger = get_logger("bigrag.worker")
_lock = asyncio.Lock()
_initialized = False
_storage = None
_heartbeat_task: asyncio.Task | None = None
_vector_store_settings: tuple[object, ...] | None = None
_HEARTBEAT_SECONDS = 30
_HEARTBEAT_TTL_SECONDS = 120
_SKIP_MIGRATIONS_ENV = "BIGRAG_WORKER_RUNTIME_SKIP_MIGRATIONS"
_RUNTIME_SETTING_KEYS = (
    "ingestion_workers",
    "turbopuffer_api_key",
    "turbopuffer_base_url",
    "turbopuffer_namespace_prefix",
    "turbopuffer_region",
)
_DEFAULT_QUEUES = {
    INGESTION_QUEUE,
    CONNECTORS_QUEUE,
    WEBHOOKS_QUEUE,
    BACKUPS_QUEUE,
    MAINTENANCE_QUEUE,
}


async def ensure_worker_runtime() -> None:
    global _initialized, _storage
    async with _lock:
        if _initialized:
            await _sync_runtime_settings()
            await start_worker_heartbeat()
            return
        settings = config_module.settings
        configure_logging(log_level=settings.log_level, log_format=settings.log_format)
        logger.info("worker starting", version=__version__, env=settings.env)
        check_production_safety(settings)
        crypto.configure(settings.master_key, previous_keys=list(settings.master_key_previous))
        await db_module.configure(
            settings.database_url,
            pool_min=settings.db_pool_min,
            pool_max=settings.db_pool_max,
        )
        if os.environ.get(_SKIP_MIGRATIONS_ENV) == "1":
            logger.info("worker migrations already complete")
        else:
            await run_migrations()
            configure_logging(log_level=settings.log_level, log_format=settings.log_format)
            logger.info("worker migrations complete")
        runtime = await runtime_settings.get_values(list(_RUNTIME_SETTING_KEYS))
        logger.info("worker runtime settings loaded")
        await _sync_vector_store(runtime)
        _storage = await init_storage_from_runtime(upload_dir=settings.upload_dir)
        await redis_cache.connect(settings.redis_url)
        await event_bus.connect(settings.redis_url)
        ingestion_queue._num_workers = runtime["ingestion_workers"]
        await ingestion_queue.connect(settings.redis_url)
        ingestion_queue.bind_vector_store(vector_store)
        await ingestion_queue.start()
        await get_conversion_executor()
        logger.info("worker queues ready")
        _initialized = True
        await start_worker_heartbeat()
        logger.info("worker ready")


async def _sync_runtime_settings() -> None:
    runtime = await runtime_settings.get_values(list(_RUNTIME_SETTING_KEYS))
    ingestion_queue._num_workers = runtime["ingestion_workers"]
    await _sync_vector_store(runtime)


async def _sync_vector_store(runtime: dict[str, Any]) -> None:
    global _vector_store_settings
    settings = (
        runtime["turbopuffer_api_key"],
        runtime["turbopuffer_base_url"],
        runtime["turbopuffer_namespace_prefix"],
        runtime["turbopuffer_region"],
    )
    if settings == _vector_store_settings:
        return
    if _vector_store_settings is not None:
        await vector_store.close()
    vector_store.configure(
        turbopuffer_api_key=runtime["turbopuffer_api_key"],
        turbopuffer_base_url=runtime["turbopuffer_base_url"],
        turbopuffer_region=runtime["turbopuffer_region"],
        turbopuffer_namespace_prefix=runtime["turbopuffer_namespace_prefix"],
    )
    if runtime["turbopuffer_api_key"]:
        try:
            vector_store.connect()
            await vector_store.health_check()
            logger.info("worker vector store ready")
        except Exception as exc:
            logger.warning(
                "worker vector store connection failed; worker will continue degraded",
                provider="turbopuffer",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
    else:
        logger.warning("worker vector store not configured", provider="turbopuffer")
    _vector_store_settings = settings
    ingestion_queue.bind_vector_store(vector_store)


async def record_worker_heartbeat() -> None:
    redis = ingestion_queue.redis
    if redis is not None:
        heartbeat = datetime.now(UTC).isoformat()
        queue_names = _worker_queue_names()
        if INGESTION_QUEUE in queue_names:
            await redis.set(WORKER_HEARTBEAT_KEY, heartbeat, ex=_HEARTBEAT_TTL_SECONDS)
        for queue_name in queue_names:
            await redis.set(
                worker_heartbeat_key(queue_name),
                heartbeat,
                ex=_HEARTBEAT_TTL_SECONDS,
            )


async def start_worker_heartbeat() -> None:
    global _heartbeat_task
    await record_worker_heartbeat()
    if _heartbeat_task is None or _heartbeat_task.done():
        _heartbeat_task = asyncio.create_task(_worker_heartbeat_loop())


async def stop_worker_heartbeat() -> None:
    global _heartbeat_task
    if _heartbeat_task is None:
        return
    _heartbeat_task.cancel()
    try:
        await _heartbeat_task
    except asyncio.CancelledError:
        pass
    _heartbeat_task = None


async def _worker_heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(_HEARTBEAT_SECONDS)
        try:
            await record_worker_heartbeat()
        except Exception as exc:
            logger.warning("worker heartbeat failed", error=repr(exc))


def _worker_queue_names() -> set[str]:
    raw = os.environ.get("BIGRAG_WORKER_QUEUES")
    if raw is None:
        return set(_DEFAULT_QUEUES)
    return {queue_name for queue_name in raw.split(",") if queue_name}
