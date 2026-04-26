from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config

from alembic import command
from bigrag.logging import get_logger

logger = get_logger("bigrag.db.bootstrap")


def _alembic_config() -> Config:
    pkg_dir = Path(__file__).resolve().parent.parent
    bundled = pkg_dir / "_alembic"
    if (bundled / "env.py").exists():
        ini_path = bundled / "alembic.ini"
        script_dir = bundled
    else:
        api_root = pkg_dir.parent
        ini_path = api_root / "alembic.ini"
        script_dir = api_root / "alembic"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(script_dir))
    return cfg


async def run_migrations() -> None:
    cfg = _alembic_config()
    loop = asyncio.get_running_loop()
    logger.info("running alembic upgrade head")
    await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))
    logger.info("migrations complete")
