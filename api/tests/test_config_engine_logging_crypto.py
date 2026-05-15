from __future__ import annotations

import asyncio
import importlib
import logging
import ssl
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from bigrag import config
from bigrag.logging import RequestLoggingMiddleware, configure_logging, redact_secrets
from bigrag.services import crypto

db_engine = importlib.import_module("bigrag.db.engine")


def test_settings_from_toml_flattens_sections_and_respects_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "bigrag.toml"
    settings_path.write_text(
        "\n".join(
            [
                'log_level = "info"',
                "run_migrations = false",
                "[database]",
                'url = "postgres://toml"',
                "[db]",
                "pool_min = 2",
                "[conversion]",
                "pdf_ocr_enabled = false",
            ]
        )
    )
    monkeypatch.setenv("BIGRAG_DATABASE_URL", "postgres://env")

    settings = config.Settings.from_toml(settings_path)

    assert settings.database_url == "postgres://env"
    assert settings.db_pool_min == 2
    assert settings.conversion_pdf_ocr_enabled is False
    assert settings.log_level == "info"
    assert settings.log_format == "text"
    assert config.Settings.from_toml(tmp_path / "missing.toml").database_url.startswith(
        "postgres://"
    )


def test_settings_accepts_logging_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIGRAG_LOG_LEVEL", "warning")
    monkeypatch.setenv("BIGRAG_LOG_FORMAT", "json")

    settings = config.Settings()

    assert settings.log_level == "warning"
    assert settings.log_format == "json"


def test_db_engine_normalizes_urls_and_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(db_engine, "_engine", None)
    monkeypatch.setattr(db_engine, "_session_factory", None)

    url, connect_args = db_engine._normalize_url(
        "postgres://user:pass@localhost:5432/db?sslmode=disable&application_name=bigrag"
    )

    assert url == "postgresql+asyncpg://user:pass@localhost:5432/db?application_name=bigrag"
    assert connect_args == {"ssl": False}
    require_url, require_connect_args = db_engine._normalize_url(
        "postgres://localhost/db?sslmode=require"
    )
    verify_url, verify_connect_args = db_engine._normalize_url(
        "postgres://localhost/db?sslmode=verify-full"
    )
    assert require_url == "postgresql+asyncpg://localhost/db"
    assert require_connect_args == {"ssl": True}
    assert verify_url == "postgresql+asyncpg://localhost/db"
    assert isinstance(verify_connect_args["ssl"], ssl.SSLContext)
    assert (
        db_engine._normalize_url("postgresql://localhost/db")[0]
        == "postgresql+asyncpg://localhost/db"
    )
    with pytest.raises(RuntimeError, match="not configured"):
        db_engine.engine()
    with pytest.raises(RuntimeError, match="not configured"):
        db_engine.session_factory()


def test_db_engine_configure_clamps_pool_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    created = []
    fake_engine = FakeEngine()

    def fake_create_async_engine(url: str, **kwargs):
        created.append((url, kwargs))
        return fake_engine

    def fake_sessionmaker(engine, **kwargs):
        return {"engine": engine, "kwargs": kwargs}

    monkeypatch.setattr(db_engine, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(db_engine, "async_sessionmaker", fake_sessionmaker)

    async def run() -> None:
        await db_engine.configure(
            "postgres://localhost/db?sslmode=disable",
            pool_min=10,
            pool_max=3,
        )
        assert db_engine.engine() is fake_engine
        assert db_engine.session_factory()["engine"] is fake_engine
        await db_engine.close()

    asyncio.run(run())

    assert created[0][0] == "postgresql+asyncpg://localhost/db"
    assert created[0][1]["pool_size"] == 3
    assert created[0][1]["max_overflow"] == 0
    assert created[0][1]["connect_args"] == {"ssl": False}
    assert fake_engine.disposed is True


def test_logging_redacts_nested_secrets_and_configures_levels() -> None:
    event = {
        "api_key": "sk-live",
        "nested": [{"password": "pw", "refresh_token": "rt", "safe": "ok"}],
        "tupled": ({"authorization": "Bearer secret", "token": "secret"},),
        "set-cookie": "cookie",
    }

    redacted = redact_secrets(None, None, event)

    assert redacted == {
        "api_key": "[REDACTED]",
        "nested": [{"password": "[REDACTED]", "refresh_token": "[REDACTED]", "safe": "ok"}],
        "tupled": ({"authorization": "[REDACTED]", "token": "[REDACTED]"},),
        "set-cookie": "[REDACTED]",
    }

    configure_logging("debug", "json")
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("qdrant_client").level == logging.INFO
    assert logging.getLogger("httpcore").level == logging.WARNING

    configure_logging("not-a-level", "text")
    assert logging.getLogger().level == logging.INFO


def test_request_logging_middleware_logs_http_and_passes_through_non_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []

    class FakeLogger:
        def info(self, event: str, **kwargs) -> None:
            events.append((event, kwargs))

    async def app(scope, _receive, send) -> None:
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 204})

    monkeypatch.setattr("bigrag.logging.get_logger", lambda _name: FakeLogger())
    middleware = RequestLoggingMiddleware(app)

    async def run() -> None:
        sent = []

        async def send(message) -> None:
            sent.append(message)

        await middleware(
            {
                "type": "http",
                "method": "GET",
                "path": "/health",
                "headers": [(b"x-request-id", b"rid-123")],
            },
            lambda: None,
            send,
        )
        await middleware({"type": "lifespan"}, lambda: None, send)
        assert sent[0]["headers"] == [(b"x-request-id", b"rid-123")]

    asyncio.run(run())

    assert events[0] == (
        "request_start",
        {"method": "GET", "path": "/health", "request_id": "rid-123"},
    )
    assert events[1][0] == "request"
    assert events[1][1]["status"] == 204
    assert events[1][1]["request_id"] == "rid-123"


def test_crypto_encrypts_decrypts_previous_keys_and_column_values() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    other_key = Fernet.generate_key().decode()

    try:
        crypto.configure(old_key)
        old_ciphertext = crypto.encrypt("old secret")
        old_bytes = crypto.encrypt_bytes(b"old bytes")

        crypto.configure(new_key, [old_key])
        new_ciphertext = crypto.encrypt("new secret")

        assert crypto.decrypt(old_ciphertext) == "old secret"
        assert crypto.decrypt(new_ciphertext) == "new secret"
        assert crypto.decrypt_bytes(old_bytes) == b"old bytes"
        assert crypto.looks_encrypted_bytes(old_bytes) is True

        column = crypto.EncryptedString()
        bound = column.process_bind_param("column secret", None)
        assert column.process_bind_param(None, None) is None
        assert column.process_result_value(bound, None) == "column secret"
        assert column.process_result_value("plain", None) == "plain"
        assert column.process_result_value(None, None) is None

        crypto.configure(other_key)
        with pytest.raises(ValueError, match="wrong BIGRAG_MASTER_KEY"):
            crypto.decrypt(old_ciphertext)
        with pytest.raises(ValueError, match="wrong BIGRAG_MASTER_KEY"):
            crypto.decrypt_bytes(old_bytes)
    finally:
        crypto.configure(None)


def test_crypto_rejects_invalid_or_missing_keys() -> None:
    try:
        crypto.configure(None)
        assert crypto.is_configured() is False
        with pytest.raises(crypto.CryptoNotConfiguredError):
            crypto.encrypt("secret")
        with pytest.raises(ValueError, match="not a valid Fernet key"):
            crypto.configure("not-a-fernet-key")
    finally:
        crypto.configure(None)
