"""On-startup migration bootstrap.

- If ``alembic_version`` table exists → run ``alembic upgrade head`` normally.
- Else if legacy ``_migrations`` table exists with >= the known baseline
  count → stamp head (existing production DB adoption; schema is at HEAD).
- Else (fresh DB) → run ``alembic upgrade head``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from bigrag.db.engine import engine
from bigrag.logging import get_logger

logger = get_logger("bigrag.db.bootstrap")

LEGACY_MIGRATION_COUNT = 21


def _alembic_config() -> Config:
    api_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    return cfg


async def _has_table(conn, name: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = :n"
        ).bindparams(n=name)
    )
    return result.scalar_one() > 0


async def _legacy_count(conn) -> int:
    result = await conn.execute(text("SELECT count(*) FROM _migrations"))
    return int(result.scalar_one())


async def run_migrations() -> None:
    cfg = _alembic_config()
    async with engine().connect() as conn:
        have_alembic = await _has_table(conn, "alembic_version")
        have_legacy = await _has_table(conn, "_migrations")
        legacy_count = await _legacy_count(conn) if have_legacy else 0

    loop = asyncio.get_running_loop()
    if not have_alembic and legacy_count >= LEGACY_MIGRATION_COUNT:
        logger.info("adopting existing schema — stamping alembic head")
        await loop.run_in_executor(None, lambda: command.stamp(cfg, "head"))
    else:
        logger.info("running alembic upgrade head")
        await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))
    logger.info("migrations complete")
