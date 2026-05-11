from __future__ import annotations

import asyncio
import importlib
import uuid

import pytest

from bigrag.db.models import InstanceSetting
from bigrag.services import runtime_settings
from bigrag.services.runtime_settings import REGISTRY, _public_value, validate_setting_value

db_engine = importlib.import_module("bigrag.db.engine")


def test_runtime_settings_validate_string_list_from_text() -> None:
    assert validate_setting_value("cors_origins", "https://a.example\nhttps://b.example") == [
        "https://a.example",
        "https://b.example",
    ]


def test_runtime_settings_reject_out_of_range_integer() -> None:
    with pytest.raises(ValueError):
        validate_setting_value("max_upload_size_mb", 0)


def test_runtime_settings_reject_invalid_select_option() -> None:
    with pytest.raises(ValueError):
        validate_setting_value("storage_backend", "ftp")


def test_runtime_settings_include_upload_session_limits() -> None:
    assert validate_setting_value("max_upload_session_files", 10000) == 10000
    assert validate_setting_value("upload_session_item_retention_hours", 168) == 168


def test_runtime_settings_reject_removed_rate_limit_settings() -> None:
    for key in (
        "auth_rate_limit_window_seconds",
        "auth_login_email_rate_limit",
        "auth_login_ip_rate_limit",
        "auth_setup_ip_rate_limit",
        "upload_rate_limit_files_per_hour",
        "upload_rate_limit_mb_per_hour",
    ):
        with pytest.raises(KeyError):
            validate_setting_value(key, 1)


def test_runtime_settings_include_embedding_cache_security_settings() -> None:
    assert validate_setting_value("embedding_cache_mode", "encrypted") == "encrypted"
    assert validate_setting_value("embedding_cache_mode", "disabled") == "disabled"
    assert validate_setting_value("embedding_cache_retention_days", 30) == 30
    assert REGISTRY["query_embedding_cache_ttl"].default == 300


def test_runtime_settings_include_backup_destination_settings() -> None:
    assert validate_setting_value("backup_s3_bucket", "bigrag-backups") == "bigrag-backups"
    assert validate_setting_value("backup_s3_region", "auto") == "auto"
    assert validate_setting_value("backup_s3_force_path_style", True) is True
    assert REGISTRY["backup_s3_secret_access_key"].secret is True


def test_runtime_settings_include_vector_store_settings() -> None:
    assert validate_setting_value("vector_store_provider", "qdrant") == "qdrant"
    assert validate_setting_value("vector_store_provider", "s3_vectors") == "s3_vectors"
    assert validate_setting_value("vector_store_provider", "turbopuffer") == "turbopuffer"
    assert REGISTRY["s3_vectors_secret_access_key"].secret is True
    assert REGISTRY["turbopuffer_api_key"].secret is True
    assert REGISTRY["vector_store_provider"].restart_required is True


def test_runtime_settings_include_vector_api_limits() -> None:
    assert validate_setting_value("max_vector_upsert_count", 1000) == 1000
    assert validate_setting_value("max_vector_delete_count", 10000) == 10000
    assert validate_setting_value("max_vector_text_chars", 100000) == 100000
    assert validate_setting_value("max_vector_metadata_bytes", 65536) == 65536
    assert REGISTRY["max_vector_upsert_count"].group == "ingestion"


def test_runtime_settings_reject_invalid_vector_store_provider() -> None:
    with pytest.raises(ValueError):
        validate_setting_value("vector_store_provider", "pinecone")


def test_runtime_settings_redacts_secret_public_value() -> None:
    row = InstanceSetting(key="embedding_api_key", secret_value="sk-secret")

    public = _public_value(REGISTRY["embedding_api_key"], row)

    assert public.value is None
    assert public.has_value is True


def test_runtime_settings_validate_scalar_edge_cases() -> None:
    assert validate_setting_value("session_cookie_secure", " true ") is True
    assert validate_setting_value("session_cookie_secure", "false") is False
    assert validate_setting_value("max_upload_size_mb", "") == 64
    assert validate_setting_value("qdrant_search_ef", "") is None
    assert validate_setting_value("chat_temperature", "1.5") == 1.5
    assert validate_setting_value("session_cookie_domain", "") is None
    assert validate_setting_value("embedding_api_key", "") is None
    assert validate_setting_value("webhook_retry_delays", "1\n2, 3") == [1, 2, 3]

    invalid_cases = [
        ("session_cookie_secure", "yes", "boolean"),
        ("max_upload_size_mb", True, "integer"),
        ("max_upload_size_mb", "bad", "integer"),
        ("chat_temperature", True, "number"),
        ("chat_temperature", "bad", "number"),
        ("webhook_retry_delays", "1,bad", "integer values"),
    ]
    for key, value, message in invalid_cases:
        with pytest.raises(ValueError, match=message):
            validate_setting_value(key, value)


def test_runtime_settings_public_update_and_reset(fake_session) -> None:
    actor_id = uuid.uuid4()
    existing = InstanceSetting(
        key="session_cookie_secure",
        value=False,
        secret_value=None,
        updated_by=actor_id,
    )
    secret = InstanceSetting(key="embedding_api_key", secret_value="sk-live")
    fake_session.scalars_values = [[existing, secret], [existing]]

    async def run() -> None:
        public = await runtime_settings.get_public_settings(fake_session)
        changed = await runtime_settings.update_settings(
            fake_session,
            {
                "session_cookie_secure": True,
                "embedding_api_key": "sk-new",
            },
            updated_by=actor_id,
        )
        reset = await runtime_settings.reset_settings(fake_session, ["session_cookie_secure"])

        assert public.values["session_cookie_secure"].value is False
        assert public.values["session_cookie_secure"].source == "database"
        assert public.values["embedding_api_key"].value is None
        assert public.values["embedding_api_key"].has_value is True
        assert changed == ["session_cookie_secure", "embedding_api_key"]
        assert existing.value is True
        assert fake_session.added[0].key == "embedding_api_key"
        assert fake_session.added[0].secret_value == "sk-new"
        assert reset == ["session_cookie_secure"]

    asyncio.run(run())
    assert fake_session.commits == 2


def test_runtime_settings_update_and_reset_reject_unknown_keys(fake_session) -> None:
    async def run() -> None:
        with pytest.raises(KeyError):
            await runtime_settings.update_settings(fake_session, {"missing": "x"}, updated_by=None)
        with pytest.raises(KeyError):
            await runtime_settings.reset_settings(fake_session, ["missing"])

    asyncio.run(run())


def test_runtime_settings_cached_values_and_sync_lookup(monkeypatch, fake_session) -> None:
    class SessionContext:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    fake_session.scalars_values = [[InstanceSetting(key="session_cookie_secure", value=True)]]
    monkeypatch.setattr(db_engine, "session_factory", lambda: lambda: SessionContext())
    runtime_settings.invalidate_runtime_settings_cache()

    async def run() -> None:
        values = await runtime_settings.get_values(["session_cookie_secure"])
        all_values = await runtime_settings.all_runtime_values()

        assert values == {"session_cookie_secure": True}
        assert all_values["session_cookie_secure"] is True
        assert runtime_settings.sync_value("session_cookie_secure") is True

    asyncio.run(run())

    runtime_settings.invalidate_runtime_settings_cache()
    assert runtime_settings.sync_value("session_cookie_secure") is False
