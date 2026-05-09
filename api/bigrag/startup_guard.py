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

    if not s.session_cookie_secure:
        problems.append(
            "BIGRAG_SESSION_COOKIE_SECURE must be true in BIGRAG_ENV=prod so "
            "admin session cookies are only sent over HTTPS."
        )

    if s.session_cookie_samesite == "none" and not s.session_cookie_secure:
        problems.append(
            "BIGRAG_SESSION_COOKIE_SAMESITE=none requires BIGRAG_SESSION_COOKIE_SECURE=true."
        )

    if s.host in {"0.0.0.0", "::"} and not s.allow_public_bind_in_prod:
        problems.append(
            "BIGRAG_HOST binds to every interface in prod. Set "
            "BIGRAG_ALLOW_PUBLIC_BIND_IN_PROD=true after confirming a TLS reverse "
            "proxy or network boundary protects the service."
        )

    if s.session_cookie_domain and not s.trusted_proxies:
        problems.append(
            "BIGRAG_SESSION_COOKIE_DOMAIN is set but BIGRAG_TRUSTED_PROXIES is empty. "
            "Configure trusted proxy CIDRs before relying on forwarded browser origins."
        )

    if not problems:
        logger.info("startup guard: production checks passed")
        return

    logger.error(
        "Refusing to start in BIGRAG_ENV=prod with insecure defaults:",
    )
    for index, line in enumerate(problems, 1):
        logger.error("startup guard failed", index=index, problem=line)
    logger.error(
        "Set BIGRAG_ENV=dev if you really intend to run in this state, or fix the items above.",
    )
    sys.exit(1)
