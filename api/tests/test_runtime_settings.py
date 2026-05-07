from __future__ import annotations

import pytest

from bigrag.db.models import InstanceSetting
from bigrag.services.runtime_settings import REGISTRY, _public_value, validate_setting_value


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


def test_runtime_settings_redacts_secret_public_value() -> None:
    row = InstanceSetting(key="embedding_api_key", secret_value="sk-secret")

    public = _public_value(REGISTRY["embedding_api_key"], row)

    assert public.value is None
    assert public.has_value is True
