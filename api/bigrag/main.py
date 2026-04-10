from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bigrag import __version__
from bigrag.config import Settings, settings
from bigrag.database import db
from bigrag.exceptions import ConflictError, NotFoundError, ValidationError
from bigrag.logging import RequestLoggingMiddleware, configure_logging, get_logger
from bigrag.services import redis_cache
from bigrag.services.event_bus import event_bus
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import init_storage
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import WebhookDispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings

    configure_logging(log_level=s.log_level, log_format=s.log_format)
    logger = get_logger("bigrag")
    logger.info("starting", version=__version__)

    if not s.api_secret:
        logger.warning("api_secret not set, all endpoints are open")
    if s.cors_origins == ["*"]:
        logger.warning("CORS allows all origins, restrict in production")

    # Postgres
    await db.connect(s.database_url, min_size=s.db_pool_min, max_size=s.db_pool_max)
    await db.migrate()
    app.state.db = db

    # Milvus
    vector_store.configure(s.milvus_uri, nprobe=s.milvus_nprobe)
    vector_store.connect()
    app.state.vector_store = vector_store

    # Storage
    storage = init_storage(
        backend=s.storage_backend,
        upload_dir=s.upload_dir,
        s3_bucket=s.s3_bucket,
        s3_endpoint_url=s.s3_endpoint_url,
        s3_region=s.s3_region,
        s3_access_key=s.s3_access_key,
        s3_secret_key=s.s3_secret_key,
    )
    app.state.storage = storage

    # Redis cache + event bus
    await redis_cache.connect(s.redis_url)
    await event_bus.connect(s.redis_url)

    # Redis + ingestion queue
    ingestion_queue._num_workers = s.ingestion_workers
    await ingestion_queue.connect(s.redis_url)
    await ingestion_queue.start(db=db, vector_store=vector_store)
    app.state.queue = ingestion_queue

    # Webhook dispatcher
    dispatcher = WebhookDispatcher()
    await dispatcher.start()
    app.state.webhook_dispatcher = dispatcher

    # Resume incomplete S3 ingest jobs
    from bigrag.services.s3_ingest import resume_incomplete_jobs

    await resume_incomplete_jobs()

    # Cleanup task
    import asyncio

    from bigrag.services.cleanup import cleanup_old_data

    cleanup_task = asyncio.create_task(cleanup_old_data(db))

    logger.info("server ready", host=s.host, port=s.port)
    yield

    cleanup_task.cancel()
    await ingestion_queue.stop()
    await dispatcher.stop()
    await event_bus.close()
    await redis_cache.close()
    await storage.close()
    vector_store.close()
    await db.close()
    logger.info("shut down")


def create_app(settings_override: Settings | None = None) -> FastAPI:
    s = settings_override or settings

    app = FastAPI(
        title="bigRAG",
        description="Self-hostable RAG platform with Docling + Milvus",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = s

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handlers for domain exceptions
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    from bigrag.routers.collections import router as collections_router
    from bigrag.routers.documents import global_router as documents_global_router
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.health import router as health_router
    from bigrag.routers.query import router as query_router
    from bigrag.routers.s3_jobs import router as s3_jobs_router
    from bigrag.routers.webhooks import router as webhooks_router

    app.include_router(health_router)
    app.include_router(collections_router)
    app.include_router(documents_router)
    app.include_router(documents_global_router)
    app.include_router(query_router)
    app.include_router(s3_jobs_router)
    app.include_router(webhooks_router)

    return app


def cli():
    parser = argparse.ArgumentParser(description="bigRAG server")
    parser.add_argument("--config", default="bigrag.toml", help="Config file path")
    parser.add_argument("--host", help="Server host")
    parser.add_argument("--port", type=int, help="Server port")
    parser.add_argument("--database-url", help="Postgres connection URL")
    parser.add_argument("--milvus-uri", help="Milvus connection URI")
    parser.add_argument("--redis-url", help="Redis connection URL")
    parser.add_argument("--log-level", help="Log level")
    parser.add_argument("--log-format", choices=["text", "json"], help="Log format")
    args = parser.parse_args()

    from bigrag import config

    s = Settings.from_toml(args.config)

    if args.host:
        s.host = args.host
    if args.port:
        s.port = args.port
    if args.database_url:
        s.database_url = args.database_url
    if args.milvus_uri:
        s.milvus_uri = args.milvus_uri
    if args.redis_url:
        s.redis_url = args.redis_url
    if args.log_level:
        s.log_level = args.log_level
    if args.log_format:
        s.log_format = args.log_format

    config.settings = s

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
