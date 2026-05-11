from __future__ import annotations

import asyncio
from importlib import import_module
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from rag_computer.config import settings
from rag_computer.db.base import Base
from rag_computer.db.engine import _normalize_url
from rag_computer.logging import get_logger

import_module("rag_computer.db.models")

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
logger = get_logger("rag_computer.db.migrations")

ADVISORY_LOCK_KEY = 8675309
LOCK_TIMEOUT_SECONDS = 60
STATEMENT_TIMEOUT_SECONDS = 300


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
    connection.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT_SECONDS}s'"))
    connection.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'"))
    logger.info("acquiring migration lock", lock_key=ADVISORY_LOCK_KEY)
    acquired = connection.scalar(
        text("SELECT pg_try_advisory_lock(:k)").bindparams(k=ADVISORY_LOCK_KEY)
    )
    if not acquired:
        raise RuntimeError(
            "Could not acquire the rag.computer migration lock. Another API deployment or "
            "worker is probably still running migrations; stop old API deployments or "
            "set RAG_COMPUTER_WORKERS=1, then redeploy."
        )
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
