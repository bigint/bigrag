from __future__ import annotations

import argparse
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from bigrag import __version__
from bigrag.config import Settings, settings
from bigrag.database import db
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage, init_storage
from bigrag.services.vector_store import vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
            if settings.log_format == "text"
            else (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","msg":"%(message)s"}'
            )
        )
    )
    logging.root.handlers.clear()
    logging.root.addHandler(handler)
    logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger = logging.getLogger("bigrag")
    logger.info(f"bigRAG v{__version__} starting")

    if not settings.secret_key:
        logger.warning(
            "BIGRAG_SECRET_KEY is not set. "
            "Embedding API keys stored in collections will fail to encrypt. "
            "Set BIGRAG_SECRET_KEY to a random string before creating collections."
        )

    # Postgres
    await db.connect(
        settings.database_url,
        min_size=settings.db_pool_min,
        max_size=settings.db_pool_max,
    )
    await db.migrate()

    # Milvus
    vector_store.configure(settings.milvus_uri, nprobe=settings.milvus_nprobe)
    vector_store.connect()

    # Storage
    init_storage(
        backend=settings.storage_backend,
        upload_dir=settings.upload_dir,
        s3_bucket=settings.s3_bucket,
        s3_endpoint_url=settings.s3_endpoint_url,
        s3_region=settings.s3_region,
        s3_access_key=settings.s3_access_key,
        s3_secret_key=settings.s3_secret_key,
    )

    # Redis + ingestion queue
    ingestion_queue._num_workers = settings.ingestion_workers
    await ingestion_queue.connect(settings.redis_url)
    await ingestion_queue.start()

    # Webhook dispatcher
    from bigrag.services.webhook import webhook_dispatcher

    await webhook_dispatcher.start()

    logger.info(f"Server ready on {settings.host}:{settings.port}")
    yield

    await ingestion_queue.stop()
    from bigrag.services.webhook import webhook_dispatcher

    await webhook_dispatcher.stop()
    await get_storage().close()
    vector_store.close()
    await db.close()
    logger.info("bigRAG shut down")


request_logger = logging.getLogger("bigrag.http")


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        path = scope["path"]
        method = scope["method"]
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        elapsed = (time.monotonic() - start) * 1000
        request_logger.info(f"← {method} {path} {status_code} {elapsed:.0f}ms")


def create_app() -> FastAPI:
    app = FastAPI(
        title="bigRAG",
        description="Self-hostable RAG platform with Docling + Milvus",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from bigrag.middleware.auth import get_current_user

    Instrumentator().instrument(app).expose(
        app, endpoint="/v1/metrics", dependencies=[Depends(get_current_user)]
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready")
    async def readiness():
        checks = {"version": __version__}
        healthy = True

        try:
            await db.fetchrow("SELECT 1")
            checks["postgres"] = True
        except Exception:
            checks["postgres"] = False
            healthy = False

        checks["milvus"] = vector_store.client is not None
        if not checks["milvus"]:
            healthy = False

        try:
            await ingestion_queue._redis.ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
            healthy = False

        status = "ok" if healthy else "degraded"
        checks["status"] = status
        from fastapi.responses import JSONResponse

        return JSONResponse(content=checks, status_code=200 if healthy else 503)

    @app.get("/v1/queue/stats")
    async def queue_stats(_: dict = Depends(get_current_user)):
        return await ingestion_queue.stats

    from bigrag.routers.collections import router as collections_router
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.query import router as query_router

    app.include_router(collections_router)
    app.include_router(documents_router)
    app.include_router(query_router)

    from bigrag.routers.webhooks import router as webhooks_router

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
    parser.add_argument("--secret-key", help="Encryption key for secrets at rest")
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
    if args.secret_key:
        s.secret_key = args.secret_key
    if args.log_level:
        s.log_level = args.log_level
    if args.log_format:
        s.log_format = args.log_format

    config.settings = s

    # Use factory=True so the app is created AFTER config overrides are applied.
    # Without this, module-level app creation uses default settings, ignoring
    # CLI/TOML config for CORS origins and other middleware settings.
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
