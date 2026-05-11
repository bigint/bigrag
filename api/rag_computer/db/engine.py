from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from rag_computer.logging import get_logger

logger = get_logger("rag_computer.db")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_url(dsn: str) -> tuple[str, dict]:
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    connect_args: dict = {}
    parsed = urlparse(dsn)
    if parsed.query:
        params = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
        kept = [(k, v) for k, v in params if k != "sslmode"]
        sslmode = next((v for k, v in params if k == "sslmode"), None)
        if sslmode == "disable":
            connect_args["ssl"] = False
        parsed = parsed._replace(query=urlencode(kept))
        dsn = urlunparse(parsed)
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn, connect_args


async def configure(database_url: str, pool_min: int = 5, pool_max: int = 50) -> None:
    global _engine, _session_factory
    url, connect_args = _normalize_url(database_url)
    if pool_min > pool_max:
        pool_min = pool_max
    overflow = max(0, pool_max - pool_min)
    _engine = create_async_engine(
        url,
        pool_size=pool_min,
        max_overflow=overflow,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
        future=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    logger.info("sqlalchemy engine ready", pool_min=pool_min, pool_max=pool_max)


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("db.engine not configured — call configure() first")
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("db.session_factory not configured — call configure() first")
    return _session_factory


async def close() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    logger.info("SQLAlchemy engine closed")
