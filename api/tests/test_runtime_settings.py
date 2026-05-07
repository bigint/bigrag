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


def test_runtime_settings_redacts_secret_public_value() -> None:
    row = InstanceSetting(key="embedding_api_key", secret_value="sk-secret")

    public = _public_value(REGISTRY["embedding_api_key"], row)

    assert public.value is None
    assert public.has_value is True
