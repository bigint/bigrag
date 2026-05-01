from __future__ import annotations

from bigrag import config as config_module
from bigrag.config import Settings
from bigrag.main import _CLI_CONFIG_PATH_ENV, _CLI_OVERRIDES_ENV, create_app


def test_env_overrides_toml(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "bigrag.toml"
    config_path.write_text('port = 4444\nembedding_base_url = "http://toml.example/v1"\n')
    monkeypatch.setenv("BIGRAG_PORT", "5555")

    settings = Settings.from_toml(config_path)

    assert settings.port == 5555
    assert settings.embedding_base_url == "http://toml.example/v1"


def test_legacy_run_migrations_toml_key_is_ignored(tmp_path) -> None:
    config_path = tmp_path / "bigrag.toml"
    config_path.write_text("run_migrations = false\nmigration_timeout_seconds = 12\n")

    settings = Settings.from_toml(config_path)

    assert not hasattr(settings, "run_migrations")
    assert settings.migration_timeout_seconds == 12


def test_create_app_uses_runtime_settings_override(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "settings", Settings(port=4000))

    override = Settings(port=5555, cors_origins=["https://admin.example.com"])
    app = create_app(override)

    assert app.state.settings is override
    assert config_module.settings is override
    assert app.state.settings.port == 5555


def test_create_app_loads_cli_runtime_settings_from_env(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "bigrag.toml"
    config_path.write_text('port = 4444\ncors_origins = ["https://toml.example"]\n')
    monkeypatch.setenv(_CLI_CONFIG_PATH_ENV, str(config_path))
    monkeypatch.setenv(_CLI_OVERRIDES_ENV, '{"port": 5555}')
    monkeypatch.setattr(config_module, "settings", Settings(port=4000))

    app = create_app()

    assert app.state.settings.port == 5555
    assert app.state.settings.cors_origins == ["https://toml.example"]
    assert config_module.settings is app.state.settings
