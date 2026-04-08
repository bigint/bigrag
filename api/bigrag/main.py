from __future__ import annotations

import argparse
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from bigrag import __version__
from bigrag.config import Settings, settings
from bigrag.database import Database
from bigrag.exceptions import ConflictError, NotFoundError, ValidationError
from bigrag.logging import ColorFormatter, RequestLoggingMiddleware
from bigrag.services.queue import IngestionQueue
from bigrag.services.storage import StorageBackend, init_storage
from bigrag.services.vector_store import VectorStore
from bigrag.services.webhook import WebhookDispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings

    handler = logging.StreamHandler(sys.stdout)
    if s.log_format == "json":
        handler.setFormatter(
            logging.Formatter(
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","msg":"%(message)s"}'
            )
        )
    else:
        handler.setFormatter(ColorFormatter())
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(getattr(logging, s.log_level.upper(), logging.INFO))
    logger = logging.getLogger("bigrag")
    logger.info(f"bigRAG v{__version__} starting")

    if not s.api_secret:
        logger.warning(
            "BIGRAG_API_SECRET is not set — all endpoints are open without authentication"
        )
    if s.cors_origins == ["*"]:
        logger.warning(
            "CORS allows all origins (BIGRAG_CORS_ORIGINS='*') — restrict in production"
        )

    # Postgres
    db = Database()
    await db.connect(s.database_url, min_size=s.db_pool_min, max_size=s.db_pool_max)
    await db.migrate()
    app.state.db = db

    # Milvus
    vs = VectorStore()
    vs.configure(s.milvus_uri, nprobe=s.milvus_nprobe)
    vs.connect()
    app.state.vector_store = vs

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

    # Redis + ingestion queue
    queue = IngestionQueue(num_workers=s.ingestion_workers)
    await queue.connect(s.redis_url)
    await queue.start(db=db, vector_store=vs)
    app.state.queue = queue

    # Webhook dispatcher
    dispatcher = WebhookDispatcher()
    await dispatcher.start()
    app.state.webhook_dispatcher = dispatcher

    # Cleanup task
    import asyncio

    from bigrag.services.cleanup import cleanup_old_data

    cleanup_task = asyncio.create_task(cleanup_old_data(db))

    logger.info(f"Server ready on {s.host}:{s.port}")
    yield

    cleanup_task.cancel()
    await queue.stop()
    await dispatcher.stop()
    await storage.close()
    vs.close()
    await db.close()
    logger.info("bigRAG shut down")


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
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.health import router as health_router
    from bigrag.routers.query import router as query_router
    from bigrag.routers.webhooks import router as webhooks_router

    app.include_router(health_router)
    app.include_router(collections_router)
    app.include_router(documents_router)
    app.include_router(query_router)
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
