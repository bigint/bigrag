from __future__ import annotations

import asyncio
from pathlib import Path

from alembic.config import Config

from alembic import command
from rag_computer.logging import get_logger

logger = get_logger("rag_computer.db.bootstrap")


def _alembic_config() -> Config:
    pkg_dir = Path(__file__).resolve().parent.parent
    bundled = pkg_dir / "_alembic"
    api_root = pkg_dir.parent
    candidates = (
        (bundled / "alembic.ini", bundled),
        (api_root / "alembic.ini", api_root / "alembic"),
    )
    for ini_path, script_dir in candidates:
        if ini_path.exists() and (script_dir / "env.py").exists():
            break
    else:
        searched = ", ".join(str(script_dir) for _, script_dir in candidates)
        raise FileNotFoundError(f"Alembic env.py was not found in: {searched}")

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(script_dir))
    return cfg


async def run_migrations() -> None:
    cfg = _alembic_config()
    loop = asyncio.get_running_loop()
    logger.info("running alembic upgrade head")
    await loop.run_in_executor(None, lambda: command.upgrade(cfg, "head"))
    logger.info("migrations complete")
