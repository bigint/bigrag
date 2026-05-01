from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomli
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIGRAG_", env_nested_delimiter="__")

    env: Literal["dev", "prod"] = "dev"

    host: str = "0.0.0.0"
    port: int = 4000
    workers: int = 1
    cors_origins: list[str] = []
    trusted_proxies: list[str] = []

    database_url: str = "postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
    db_pool_min: int = 5
    db_pool_max: int = 50
    migration_timeout_seconds: int = 60

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_connect_timeout_seconds: int = 10
    qdrant_required: bool = False

    redis_url: str = "redis://localhost:6379/0"

    master_key: str | None = None
    master_key_previous: list[str] = []

    session_expiry_hours: int = 168
    session_cookie_name: str = "bigrag_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_domain: str | None = None

    embedding_concurrency: int = 8
    qdrant_search_ef: int | None = None
    collection_cache_ttl: int = 30
    queue_max_depth: int = 10000
    conversion_timeout: int = 300
    webhook_delivery_timeout: int = 10
    webhook_retry_delays: list[int] = [10, 30, 90]
    webhook_cache_ttl: int = 60
    webhook_max_count: int = 50

    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None

    upload_dir: str = "./data/uploads"

    max_upload_size_mb: int = 1024
    ingestion_workers: int = 4
    ingestion_batch_size: int = 128

    _log_level: str = PrivateAttr(default="info")
    _log_format: str = PrivateAttr(default="text")

    @property
    def log_level(self) -> str:
        return self._log_level

    @log_level.setter
    def log_level(self, value: str) -> None:
        self._log_level = value

    @property
    def log_format(self) -> str:
        return self._log_format

    @log_format.setter
    def log_format(self, value: str) -> None:
        self._log_format = value

    @classmethod
    def from_toml(cls, path: str | Path) -> Settings:
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "rb") as f:
            data = tomli.load(f)
        flat: dict = {}
        for section, values in data.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    key = f"{section}_{k}"
                    if f"BIGRAG_{key.upper()}" not in os.environ:
                        flat[key] = v
            else:
                if f"BIGRAG_{section.upper()}" not in os.environ:
                    flat[section] = values
        log_level = flat.pop("log_level", None)
        log_format = flat.pop("log_format", None)
        flat.pop("run_migrations", None)
        settings = cls(**flat)
        if isinstance(log_level, str):
            settings.log_level = log_level
        if isinstance(log_format, str):
            settings.log_format = log_format
        return settings


settings = Settings()
