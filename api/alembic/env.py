"""Alembic env — async, reads DSN from bigrag settings, holds an advisory
lock while migrating so multi-instance rollouts don't race the DDL."""

from __future__ import annotations

import asyncio
from importlib import import_module
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from bigrag.config import settings
from bigrag.db.base import Base
from bigrag.logging import get_logger

import_module("bigrag.db.models")

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
logger = get_logger("bigrag.db.migrations")

ADVISORY_LOCK_KEY = 8675309
LOCK_TIMEOUT_SECONDS = 60
STATEMENT_TIMEOUT_SECONDS = 300


def _build_url() -> str:
    dsn = settings.database_url
    if "sslmode=disable" in dsn:
        dsn = dsn.replace("?sslmode=disable", "").replace("&sslmode=disable", "")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql+asyncpg://", 1)
    return dsn


def run_migrations_offline() -> None:
    context.configure(
        url=_build_url(),
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
            "Could not acquire the bigRAG migration lock. Another API deployment or "
            "worker is probably still running migrations; stop old API deployments or "
            "set BIGRAG_WORKERS=1, then redeploy."
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
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _build_url()
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
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
