from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime

from bigrag import __version__
from bigrag import config as config_module
from bigrag import db as db_module
from bigrag.db.bootstrap import run_migrations
from bigrag.logging import configure_logging, get_logger
from bigrag.services import crypto, redis_cache, runtime_settings
from bigrag.services.conversion import get_conversion_executor
from bigrag.services.event_bus import event_bus
from bigrag.services.jobs.broker import WORKER_HEARTBEAT_KEY
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import init_storage_from_runtime
from bigrag.services.vector_store import vector_store
from bigrag.startup_guard import check_production_safety

logger = get_logger("bigrag.worker")
_lock = asyncio.Lock()
_thread_lock = threading.Lock()
_initialized = False
_storage = None


async def ensure_worker_runtime() -> None:
    global _initialized, _storage
    if _initialized:
        await record_worker_heartbeat()
        return
    with _thread_lock:
        if _initialized:
            await record_worker_heartbeat()
            return
    async with _lock:
        if _initialized:
            await record_worker_heartbeat()
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
        await run_migrations()
        runtime = await runtime_settings.get_values(
            [
                "ingestion_workers",
                "qdrant_connect_timeout_seconds",
                "qdrant_required",
                "qdrant_search_ef",
                "qdrant_url",
                "turbopuffer_api_key",
                "turbopuffer_namespace_prefix",
                "turbopuffer_region",
            ]
        )
        vector_store.configure(
            qdrant_url=runtime["qdrant_url"],
            connect_timeout_seconds=runtime["qdrant_connect_timeout_seconds"],
            search_ef=runtime["qdrant_search_ef"],
            turbopuffer_api_key=runtime["turbopuffer_api_key"],
            turbopuffer_region=runtime["turbopuffer_region"],
            turbopuffer_namespace_prefix=runtime["turbopuffer_namespace_prefix"],
        )
        vector_store.connect()
        await vector_store.health_check()
        _storage = await init_storage_from_runtime(upload_dir=settings.upload_dir)
        await redis_cache.connect(settings.redis_url)
        await event_bus.connect(settings.redis_url)
        ingestion_queue._num_workers = runtime["ingestion_workers"]
        await ingestion_queue.connect(settings.redis_url)
        ingestion_queue.bind_vector_store(vector_store)
        await get_conversion_executor()
        _initialized = True
        await record_worker_heartbeat()
        logger.info("worker ready")


async def record_worker_heartbeat() -> None:
    redis = ingestion_queue.redis
    if redis is not None:
        await redis.set(WORKER_HEARTBEAT_KEY, datetime.now(UTC).isoformat(), ex=120)
