from __future__ import annotations

import sys

from bigrag.config import Settings
from bigrag.logging import get_logger

logger = get_logger("bigrag.startup")


def check_production_safety(s: Settings) -> None:

    if s.env != "prod":
        return

    problems: list[str] = []

    if "bigrag:bigrag@" in s.database_url:
        problems.append(
            "BIGRAG_DATABASE_URL is using the shipped default "
            "'bigrag:bigrag' credentials — rotate the Postgres password."
        )

    if not s.master_key:
        problems.append(
            "BIGRAG_MASTER_KEY is not set — required for at-rest encryption "
            "of provider credentials and embedding caches. Generate one with "
            "`python -c 'from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())'`."
        )

    if not problems:
        logger.info("startup guard: production checks passed")
        return

    logger.error(
        "Refusing to start in BIGRAG_ENV=prod with insecure defaults:",
    )
    for i, line in enumerate(problems, 1):
        logger.error(f"  {i}. {line}")
    logger.error(
        "Set BIGRAG_ENV=dev if you really intend to run in this state, or fix the items above.",
    )
    sys.exit(1)
