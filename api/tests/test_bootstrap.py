from __future__ import annotations

from pathlib import Path

from rag_computer.db.bootstrap import _alembic_config


def test_alembic_config_points_to_runnable_script_directory() -> None:
    cfg = _alembic_config()
    script_location = Path(cfg.get_main_option("script_location"))

    assert Path(cfg.config_file_name).is_file()
    assert (script_location / "env.py").is_file()
    assert (script_location / "versions").is_dir()
