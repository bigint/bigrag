from __future__ import annotations

import argparse
import json
import os

import uvicorn
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from bigrag import __version__
from bigrag import config as config_module
from bigrag.app_factory.exception_handlers import register_exception_handlers
from bigrag.app_factory.lifespan import lifespan
from bigrag.app_factory.routers import include_all_routers
from bigrag.config import Settings
from bigrag.middleware.cors import RuntimeCorsMiddleware
from bigrag.middleware.csrf import SessionCsrfMiddleware
from bigrag.middleware.idempotency import IdempotencyMiddleware
from bigrag.middleware.maintenance import MaintenanceWriteLockMiddleware
from bigrag.middleware.rate_limit import RateLimitMiddleware
from bigrag.middleware.request_logging import RequestLoggingMiddleware
from bigrag.services.access_log import AccessLogMiddleware

_CLI_CONFIG_PATH_ENV = "_BIGRAG_CLI_CONFIG_PATH"
_CLI_OVERRIDES_ENV = "_BIGRAG_CLI_OVERRIDES"


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
        description="Self-hostable RAG platform with Docling + turbopuffer",
        version=__version__,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,
    )
    app.state.settings = s

    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(MaintenanceWriteLockMiddleware)
    app.add_middleware(SessionCsrfMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RuntimeCorsMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    register_exception_handlers(app)
    include_all_routers(app)

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
