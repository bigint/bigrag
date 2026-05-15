from __future__ import annotations

import argparse
import asyncio
import json
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bigrag import __version__
from bigrag import config as config_module
from bigrag import db as db_module
from bigrag.config import Settings
from bigrag.db.bootstrap import run_migrations
from bigrag.exceptions import (
    ForbiddenError,
    NotFoundError,
    ServerError,
    UpstreamError,
    ValidationError,
)
from bigrag.logging import RequestLoggingMiddleware, configure_logging, get_logger
from bigrag.middleware.cors import RuntimeCorsMiddleware
from bigrag.middleware.csrf import SessionCsrfMiddleware
from bigrag.middleware.idempotency import IdempotencyMiddleware
from bigrag.middleware.maintenance import MaintenanceWriteLockMiddleware
from bigrag.services import crypto, redis_cache, runtime_settings
from bigrag.services.access_log import AccessLogMiddleware
from bigrag.services.event_bus import event_bus
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import init_storage_from_runtime
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import WebhookDispatcher
from bigrag.startup_guard import check_production_safety

_CLI_CONFIG_PATH_ENV = "_BIGRAG_CLI_CONFIG_PATH"
_CLI_OVERRIDES_ENV = "_BIGRAG_CLI_OVERRIDES"


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
            "qdrant_connect_timeout_seconds",
            "qdrant_required",
            "qdrant_search_ef",
            "qdrant_url",
            "turbopuffer_api_key",
            "turbopuffer_namespace_prefix",
            "turbopuffer_region",
            "vector_store_provider",
        ]
    )

    vector_store.configure(
        provider=runtime["vector_store_provider"],
        qdrant_url=runtime["qdrant_url"],
        connect_timeout_seconds=runtime["qdrant_connect_timeout_seconds"],
        search_ef=runtime["qdrant_search_ef"],
        turbopuffer_api_key=runtime["turbopuffer_api_key"],
        turbopuffer_region=runtime["turbopuffer_region"],
        turbopuffer_namespace_prefix=runtime["turbopuffer_namespace_prefix"],
    )
    try:
        vector_store.connect()
        await vector_store.health_check()
    except Exception as exc:
        logger.warning(
            "Vector store startup connection failed; API will start degraded",
            provider=runtime["vector_store_provider"],
            error_type=exc.__class__.__name__,
            error=str(exc),
        )
        if runtime["qdrant_required"]:
            raise
    app.state.vector_store = vector_store

    storage = await init_storage_from_runtime(upload_dir=s.upload_dir)
    app.state.storage = storage

    await redis_cache.connect(s.redis_url)
    await event_bus.connect(s.redis_url)

    ingestion_queue._num_workers = runtime["ingestion_workers"]
    await ingestion_queue.connect(s.redis_url)
    await ingestion_queue.start(vector_store=vector_store)
    app.state.queue = ingestion_queue

    dispatcher = WebhookDispatcher()
    await dispatcher.start()
    app.state.webhook_dispatcher = dispatcher

    from bigrag.services.google_drive import google_drive_scheduler

    await google_drive_scheduler.start()
    app.state.google_drive_scheduler = google_drive_scheduler

    from bigrag.services.cleanup import cleanup_old_data
    from bigrag.utils import safe_create_task

    cleanup_task = safe_create_task(cleanup_old_data(), name="cleanup")

    mcp_session_manager = getattr(app.state, "mcp_session_manager", None)
    mcp_cm = mcp_session_manager.run() if mcp_session_manager is not None else None
    if mcp_cm is not None:
        await mcp_cm.__aenter__()

    logger.info("server ready", host=s.host, port=s.port)
    yield

    if mcp_cm is not None:
        await mcp_cm.__aexit__(None, None, None)
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await google_drive_scheduler.stop()
    await ingestion_queue.stop()
    await dispatcher.stop()
    await event_bus.close()
    await redis_cache.close()
    await storage.close()
    await vector_store.close()
    await db_module.close()
    logger.info("shut down")


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


def _load_runtime_settings() -> Settings:
    config_path = os.environ.get(_CLI_CONFIG_PATH_ENV)
    s = Settings.from_toml(config_path) if config_path else config_module.settings

    raw_overrides = os.environ.get(_CLI_OVERRIDES_ENV)
    if raw_overrides:
        for key, value in json.loads(raw_overrides).items():
            if key in {"log_level", "log_format"}:
                continue
            setattr(s, key, value)
    return s


def create_app(settings_override: Settings | None = None) -> FastAPI:
    if settings_override is not None:
        config_module.settings = settings_override
    else:
        config_module.settings = _load_runtime_settings()
    s = config_module.settings

    app = FastAPI(
        title="bigRAG",
        description="Self-hostable RAG platform with Docling + Qdrant",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = s

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(MaintenanceWriteLockMiddleware)
    app.add_middleware(SessionCsrfMiddleware)
    app.add_middleware(RuntimeCorsMiddleware)

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(UpstreamError)
    async def upstream_handler(_request: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(ServerError)
    async def server_handler(_request: Request, exc: ServerError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    from bigrag.routers.admin_access import router as admin_access_router
    from bigrag.routers.admin_api_keys import router as admin_api_keys_router
    from bigrag.routers.admin_audit import router as admin_audit_router
    from bigrag.routers.admin_backups import router as admin_backups_router
    from bigrag.routers.admin_connectors import router as admin_connectors_router
    from bigrag.routers.admin_realtime import router as admin_realtime_router
    from bigrag.routers.admin_settings import router as admin_settings_router
    from bigrag.routers.admin_users import router as admin_users_router
    from bigrag.routers.auth import router as auth_router
    from bigrag.routers.chat import router as chat_router
    from bigrag.routers.collections import router as collections_router
    from bigrag.routers.connectors import router as connectors_router
    from bigrag.routers.documents import global_router as documents_global_router
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.embedding_presets import router as embedding_presets_router
    from bigrag.routers.evaluation import router as evaluation_router
    from bigrag.routers.health import router as health_router
    from bigrag.routers.mcp_servers import router as mcp_servers_router
    from bigrag.routers.preferences import router as preferences_router
    from bigrag.routers.query import router as query_router
    from bigrag.routers.upload_sessions import router as upload_sessions_router
    from bigrag.routers.usage import router as usage_router
    from bigrag.routers.webhooks import router as webhooks_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(preferences_router)
    app.include_router(admin_users_router)
    app.include_router(admin_api_keys_router)
    app.include_router(admin_connectors_router)
    app.include_router(admin_backups_router)
    app.include_router(admin_settings_router)
    app.include_router(admin_access_router)
    app.include_router(admin_realtime_router)
    app.include_router(mcp_servers_router)
    app.include_router(admin_audit_router)
    app.include_router(embedding_presets_router)
    app.include_router(collections_router)
    app.include_router(connectors_router)
    app.include_router(documents_router)
    app.include_router(documents_global_router)
    app.include_router(upload_sessions_router)
    app.include_router(chat_router)
    app.include_router(query_router)
    app.include_router(evaluation_router)
    app.include_router(usage_router)
    app.include_router(webhooks_router)

    from bigrag.services.mcp_http import build_mcp_http_app

    mcp_asgi, mcp_session_manager = build_mcp_http_app(app)
    app.state.mcp_session_manager = mcp_session_manager
    app.mount("/mcp", mcp_asgi)

    return app


def cli() -> None:
    parser = argparse.ArgumentParser(description="bigRAG server")
    parser.add_argument("--config", default="bigrag.toml", help="Config file path")
    parser.add_argument("--host", help="Server host")
    parser.add_argument("--port", type=int, help="Server port")
    parser.add_argument("--database-url", help="Postgres connection URL")
    parser.add_argument("--qdrant-url", help="Qdrant connection URL")
    parser.add_argument("--redis-url", help="Redis connection URL")
    args = parser.parse_args()

    s = Settings.from_toml(args.config)

    overrides: dict[str, str | int] = {}
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.database_url is not None:
        overrides["database_url"] = args.database_url
    if args.qdrant_url is not None:
        overrides["qdrant_url"] = args.qdrant_url
    if args.redis_url is not None:
        overrides["redis_url"] = args.redis_url
    for key, value in overrides.items():
        setattr(s, key, value)

    config_module.settings = s
    os.environ[_CLI_CONFIG_PATH_ENV] = args.config
    os.environ[_CLI_OVERRIDES_ENV] = json.dumps(overrides)

    uvicorn.run(
        "bigrag.main:create_app",
        host=s.host,
        port=s.port,
        log_level=s.log_level,
        workers=s.workers,
        factory=True,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    cli()
