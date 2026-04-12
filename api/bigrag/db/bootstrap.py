"""On-startup migration bootstrap.

Runs ``alembic upgrade head`` against the metadata database.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config

from alembic import command
from bigrag.logging import get_logger

logger = get_logger("bigrag.db.bootstrap")


def _alembic_config() -> Config:
    api_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    return cfg


async def run_migrations() -> None:
    cfg = _alembic_config()
    loop = asyncio.get_running_loop()
    logger.info("running alembic upgrade head")
    await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))
    logger.info("migrations complete")
