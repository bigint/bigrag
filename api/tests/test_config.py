from __future__ import annotations

from bigrag.config import Settings


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
