"""Tests for the production-mode startup safety guard."""

from __future__ import annotations

import pytest

from bigrag.config import Settings
from bigrag.startup_guard import check_production_safety


def _prod(**overrides) -> Settings:
    base = {
        "env": "prod",
        "cors_origins": ["https://app.example.com"],
        "session_cookie_secure": True,
        "database_url": "postgres://ops:strong-pw@db:5432/bigrag",
    }
    base.update(overrides)
    return Settings(**base)


def test_dev_mode_never_raises():
    # Even with every footgun armed, dev mode is a no-op.
    s = Settings(
        env="dev",
        cors_origins=["*"],
        session_cookie_secure=False,
        database_url="postgres://bigrag:bigrag@localhost:5433/bigrag",
    )
    check_production_safety(s)  # must not exit


def test_prod_with_safe_config_passes():
    check_production_safety(_prod())


def test_prod_rejects_wildcard_cors():
    s = _prod(cors_origins=["*"])
    with pytest.raises(SystemExit):
        check_production_safety(s)


def test_prod_rejects_insecure_cookie():
    s = _prod(session_cookie_secure=False)
    with pytest.raises(SystemExit):
        check_production_safety(s)


def test_prod_rejects_default_postgres_creds():
    s = _prod(database_url="postgres://bigrag:bigrag@localhost:5433/bigrag")
    with pytest.raises(SystemExit):
        check_production_safety(s)


def test_prod_reports_every_violation_before_exiting(capfd):
    """All problems are logged, not just the first — so operators fix
    the whole list in one edit instead of play whack-a-mole.

    Uses capfd because structlog's stream handler bypasses caplog.
    """
    from bigrag.logging import configure_logging

    configure_logging(log_level="info", log_format="text")
    s = _prod(
        cors_origins=["*"],
        session_cookie_secure=False,
        database_url="postgres://bigrag:bigrag@localhost:5433/bigrag",
    )
    with pytest.raises(SystemExit):
        check_production_safety(s)

    captured = capfd.readouterr()
    combined = captured.out + captured.err
    assert "CORS_ORIGINS" in combined
    assert "SESSION_COOKIE_SECURE" in combined
    assert "DATABASE_URL" in combined
