from __future__ import annotations

import asyncio
from importlib import import_module
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from bigrag.config import settings
from bigrag.db.base import Base
from bigrag.db.engine import _normalize_url
from bigrag.logging import get_logger

import_module("bigrag.db.models")

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
logger = get_logger("bigrag.db.migrations")

ADVISORY_LOCK_KEY = 8675309
STATEMENT_TIMEOUT_SECONDS = 1800


def _lock_timeout_seconds() -> int:
    configured = getattr(settings, "migration_timeout_seconds", 0) or 0
    return max(int(configured), 600)


def _database_connection() -> tuple[str, dict]:
    return _normalize_url(settings.database_url)


def run_migrations_offline() -> None:
    url, _ = _database_connection()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    lock_timeout = _lock_timeout_seconds()
    connection.execute(text(f"SET lock_timeout = '{lock_timeout}s'"))
    connection.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'"))
    logger.info("acquiring migration lock", lock_key=ADVISORY_LOCK_KEY, wait_seconds=lock_timeout)
    connection.execute(text("SELECT pg_advisory_lock(:k)").bindparams(k=ADVISORY_LOCK_KEY))
    logger.info("migration lock acquired", lock_key=ADVISORY_LOCK_KEY)
    try:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            logger.info("running alembic migrations")
            context.run_migrations()
            logger.info("alembic migrations finished")
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:k)").bindparams(k=ADVISORY_LOCK_KEY))
        logger.info("migration lock released", lock_key=ADVISORY_LOCK_KEY)


async def run_async_migrations() -> None:
    url, connect_args = _database_connection()
    connect_args = dict(connect_args)
    connect_args["command_timeout"] = float(STATEMENT_TIMEOUT_SECONDS + 60)
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
            await connection.commit()
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
