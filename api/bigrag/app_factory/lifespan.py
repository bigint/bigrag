from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bigrag import __version__
from bigrag import db as db_module
from bigrag.config import Settings
from bigrag.db.bootstrap import run_migrations
from bigrag.logging import configure_logging, get_logger
from bigrag.services import crypto, redis_cache, runtime_settings
from bigrag.services.access_log import start_access_log_flusher, stop_access_log_flusher
from bigrag.services.audit import start_audit_flusher, stop_audit_flusher
from bigrag.services.conversion import get_conversion_executor, shutdown_conversion_executor
from bigrag.services.event_bus import event_bus
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import init_storage_from_runtime
from bigrag.services.vector_store import vector_store
from bigrag.startup_guard import check_production_safety


@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings

    configure_logging(log_level=s.log_level, log_format=s.log_format)
    logger = get_logger("bigrag")
    logger.info("starting", version=__version__, env=s.env)

    check_production_safety(s)

    if "*" in s.cors_origins:
        logger.warning("CORS allows all origins, restrict in production")
    if not s.cors_origins and s.env != "dev":
        logger.warning(
            "BIGRAG_CORS_ORIGINS is empty — every cross-origin browser request will "
            "be rejected. Set it explicitly (e.g. https://admin.example.com)."
        )

    crypto.configure(s.master_key, previous_keys=list(s.master_key_previous))
    if not crypto.is_configured():
        logger.warning(
            "BIGRAG_MASTER_KEY not set — provider credentials will be stored "
            "in plaintext. Set it before promoting this instance to prod."
        )

    await db_module.configure(s.database_url, pool_min=s.db_pool_min, pool_max=s.db_pool_max)
    await _check_database_migrations(s, logger)

    runtime = await runtime_settings.get_values(
        [
            "ingestion_workers",
            "turbopuffer_api_key",
            "turbopuffer_base_url",
            "turbopuffer_namespace_prefix",
            "turbopuffer_region",
        ]
    )

    vector_store.configure(
        turbopuffer_api_key=runtime["turbopuffer_api_key"],
        turbopuffer_base_url=runtime["turbopuffer_base_url"],
        turbopuffer_region=runtime["turbopuffer_region"],
        turbopuffer_namespace_prefix=runtime["turbopuffer_namespace_prefix"],
    )
    try:
        vector_store.connect()
        await vector_store.health_check()
    except Exception as exc:
        logger.warning(
            "Vector store startup connection failed; API will start degraded",
            provider="turbopuffer",
            error_type=exc.__class__.__name__,
            error=str(exc),
        )
    app.state.vector_store = vector_store

    storage = await init_storage_from_runtime(upload_dir=s.upload_dir)
    app.state.storage = storage

    await redis_cache.connect(s.redis_url)
    await event_bus.connect(s.redis_url)

    ingestion_queue._num_workers = runtime["ingestion_workers"]
    await ingestion_queue.connect(s.redis_url)
    ingestion_queue.bind_vector_store(vector_store)
    app.state.queue = ingestion_queue

    await get_conversion_executor()

    await start_access_log_flusher()
    await start_audit_flusher()

    mcp_session_manager = getattr(app.state, "mcp_session_manager", None)
    mcp_cm = mcp_session_manager.run() if mcp_session_manager is not None else None
    if mcp_cm is not None:
        await mcp_cm.__aenter__()

    logger.info("server ready", host=s.host, port=s.port)
    try:
        yield
    finally:
        if mcp_cm is not None:
            await mcp_cm.__aexit__(None, None, None)
        await ingestion_queue.stop()
        for closer_name, closer in (
            ("cohere", _close_cohere),
            ("chat", _close_chat),
            ("embedding_models", _close_embedding_models),
            ("google_drive", _close_google_drive),
        ):
            try:
                await closer()
            except Exception as exc:
                logger.warning("shutdown close failed", target=closer_name, error=repr(exc))
        await event_bus.close()
        await redis_cache.close()
        await storage.close()
        await vector_store.close()
        await shutdown_conversion_executor()
        try:
            await stop_audit_flusher()
        except Exception as exc:
            logger.warning("shutdown close failed", target="audit_flusher", error=repr(exc))
        try:
            await stop_access_log_flusher()
        except Exception as exc:
            logger.warning("shutdown close failed", target="access_log_flusher", error=repr(exc))
        await db_module.close()
        logger.info("shut down")


async def _close_cohere() -> None:
    from bigrag.services.retrieval import close_cohere_clients

    await close_cohere_clients()


async def _close_chat() -> None:
    from bigrag.services.chat.provider import close_chat_clients

    await close_chat_clients()


async def _close_embedding_models() -> None:
    from bigrag.services.embedding import close_embedding_models

    await close_embedding_models()


async def _close_google_drive() -> None:
    from bigrag.services.connectors.google_drive_client import google_drive_client

    await google_drive_client.aclose()


async def _check_database_migrations(s: Settings, logger) -> None:
    logger.info("checking database migrations", timeout_seconds=s.migration_timeout_seconds)
    try:
        if s.migration_timeout_seconds > 0:
            await asyncio.wait_for(
                run_migrations(),
                timeout=s.migration_timeout_seconds,
            )
        else:
            await run_migrations()
    except TimeoutError:
        logger.error(
            "startup migrations timed out",
            timeout_seconds=s.migration_timeout_seconds,
        )
        raise
