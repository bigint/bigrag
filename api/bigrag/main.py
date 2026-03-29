from __future__ import annotations

import argparse
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from bigrag import __version__
from bigrag.config import Settings, settings
from bigrag.database import db
from bigrag.services.vector_store import vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s"
        if settings.log_format == "text"
        else '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    logger = logging.getLogger("bigrag")
    logger.info(f"bigRAG v{__version__} starting")

    # Connect to Postgres
    await db.connect(settings.database_url)
    await db.migrate()

    # Connect to Milvus
    vector_store.__init__(settings.milvus_uri)
    vector_store.connect()

    # Ensure upload dir exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Server ready on {settings.host}:{settings.port}")
    yield

    # Shutdown
    vector_store.close()
    await db.close()
    logger.info("bigRAG shut down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="bigRAG",
        description="Self-hostable RAG platform with Docling + Milvus",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/v1/metrics")

    # Health endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    # Register routers
    from bigrag.routers.auth import router as auth_router
    from bigrag.routers.admin import router as admin_router
    from bigrag.routers.collections import router as collections_router
    from bigrag.routers.documents import router as documents_router
    from bigrag.routers.query import router as query_router

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(collections_router)
    app.include_router(documents_router)
    app.include_router(query_router)

    return app


app = create_app()


def cli():
    parser = argparse.ArgumentParser(description="bigRAG server")
    parser.add_argument("--config", default="bigrag.toml", help="Config file path")
    parser.add_argument("--host", help="Server host")
    parser.add_argument("--port", type=int, help="Server port")
    parser.add_argument("--database-url", help="Postgres connection URL")
    parser.add_argument("--milvus-uri", help="Milvus connection URI")
    parser.add_argument("--master-key", help="Master key for admin access")
    parser.add_argument("--api-keys", help="Comma-separated API keys")
    parser.add_argument("--log-level", help="Log level (debug, info, warning, error)")
    parser.add_argument("--log-format", choices=["text", "json"], help="Log format")
    args = parser.parse_args()

    # Load from TOML first, then override with CLI args
    global settings
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
    if args.master_key:
        s.master_key = args.master_key
    if args.api_keys:
        s.api_keys = [k.strip() for k in args.api_keys.split(",")]
    if args.log_level:
        s.log_level = args.log_level
    if args.log_format:
        s.log_format = args.log_format

    # Update global settings
    config.settings = s

    uvicorn.run(
        "bigrag.main:app",
        host=s.host,
        port=s.port,
        log_level=s.log_level,
    )


if __name__ == "__main__":
    cli()
