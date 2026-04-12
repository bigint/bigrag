"""Refuse to boot in production mode with insecure defaults.

When ``BIGRAG_ENV=prod`` the lifespan calls :func:`check_production_safety`
before any service connects. Any violation exits(1) with a checklist
so operators know exactly what to set. ``dev`` mode skips all checks.

We deliberately don't try to check database passwords by connecting —
that's the database's job. We check the *configuration* surface the
operator controls: cookies, CORS, and the usual footguns in the
shipped docker-compose.yml.
"""

from __future__ import annotations

import sys

from bigrag.config import Settings
from bigrag.logging import get_logger

logger = get_logger("bigrag.startup")


def check_production_safety(s: Settings) -> None:
    """Raise :class:`SystemExit` if any production-insecure setting is
    active when ``s.env == "prod"``. No-op otherwise.
    """
    if s.env != "prod":
        return

    problems: list[str] = []

    if "*" in s.cors_origins:
        problems.append(
            "BIGRAG_CORS_ORIGINS contains '*' — set an explicit list of "
            "allowed origins (e.g. 'https://studio.example.com')."
        )

    if not s.session_cookie_secure:
        problems.append(
            "BIGRAG_SESSION_COOKIE_SECURE is false — set it to true so "
            "session cookies are only sent over HTTPS."
        )

    if "bigrag:bigrag@" in s.database_url:
        problems.append(
            "BIGRAG_DATABASE_URL is using the shipped default "
            "'bigrag:bigrag' credentials — rotate the Postgres password."
        )

    if not s.master_key:
        problems.append(
            "BIGRAG_MASTER_KEY is not set — required for at-rest encryption "
            "of provider credentials. Generate one with "
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
    # SystemExit is catchable by the caller (useful for tests) but
    # will terminate the process at the module boundary otherwise.
    sys.exit(1)
