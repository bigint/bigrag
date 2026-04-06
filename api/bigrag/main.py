from __future__ import annotations

import argparse
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bigrag import __version__
from bigrag.config import Settings, settings
from bigrag.database import db
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage, init_storage
from bigrag.services.vector_store import vector_store


class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    LEVEL_SHORT = {
        logging.DEBUG: "DBG",
        logging.INFO: "INF",
        logging.WARNING: "WRN",
        logging.ERROR: "ERR",
        logging.CRITICAL: "CRT",
    }

    def format(self, record: logging.LogRecord) -> str:
        c = self.COLORS.get(record.levelno, "")
        r = self.RESET
        lvl = self.LEVEL_SHORT.get(record.levelno, record.levelname)
        ts = self.formatTime(record, "%H:%M:%S")
        name = record.name.removeprefix("bigrag.")
        return f"\033[90m{ts}{r} {c}{lvl}{r} \033[1m{name}{r} {record.getMessage()}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
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
    logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger = logging.getLogger("bigrag")
    logger.info(f"bigRAG v{__version__} starting")

    if not settings.api_secret:
        logger.warning(
            "BIGRAG_API_SECRET is not set — all endpoints are open without authentication"
        )
    if settings.cors_origins == ["*"]:
        logger.warning(
            "CORS allows all origins (BIGRAG_CORS_ORIGINS='*') — restrict in production"
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

        try:
            if vector_store.client:
                from pymilvus import MilvusClient

                if isinstance(vector_store.client, MilvusClient):
                    vector_store.client.list_collections()
                checks["milvus"] = True
            else:
                checks["milvus"] = False
                healthy = False
        except Exception:
            checks["milvus"] = False
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

    @app.get("/v1/stats")
    async def platform_stats(_: dict = Depends(get_current_user)):
        import asyncio

        async def _db_stats():
            cols = await db.fetchrow("SELECT COUNT(*) as cnt FROM collections")
            docs = await db.fetchrow(
                "SELECT COUNT(*) as total, "
                "COALESCE(SUM(file_size), 0) as total_size, "
                "COALESCE(SUM(chunk_count), 0) as total_chunks, "
                "COALESCE(SUM(token_count), 0) as total_tokens, "
                "COUNT(*) FILTER (WHERE status = 'ready') as ready, "
                "COUNT(*) FILTER (WHERE status = 'pending') as pending, "
                "COUNT(*) FILTER (WHERE status = 'processing') as processing, "
                "COUNT(*) FILTER (WHERE status = 'failed') as failed "
                "FROM documents"
            )
            webhooks = await db.fetchrow("SELECT COUNT(*) as cnt FROM webhooks")
            return cols, docs, webhooks

        async def _queue_stats():
            return await ingestion_queue.stats

        (cols, docs, webhooks), queue = await asyncio.gather(_db_stats(), _queue_stats())

        return {
            "collections": cols["cnt"],
            "documents": {
                "total": docs["total"],
                "ready": docs["ready"],
                "pending": docs["pending"],
                "processing": docs["processing"],
                "failed": docs["failed"],
                "total_chunks": int(docs["total_chunks"]),
                "total_tokens": int(docs["total_tokens"]),
                "total_size_bytes": int(docs["total_size"]),
            },
            "webhooks": webhooks["cnt"],
            "queue": queue,
        }

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
