from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIGRAG_", env_nested_delimiter="__")

    log_level: Literal["debug", "info", "warning", "error"] = "debug"
    log_format: Literal["text", "json"] = "text"

    env: Literal["dev", "prod"] = "dev"

    host: str = "127.0.0.1"
    port: int = 4000
    workers: int = 1
    cors_origins: list[str] = []
    trusted_proxies: list[str] = []

    database_url: str = "postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
    db_pool_min: int = 5
    db_pool_max: int = 50
    migration_timeout_seconds: int = 60

    turbopuffer_api_key: str | None = None
    turbopuffer_base_url: str | None = None
    turbopuffer_region: str = "aws-us-east-1"
    turbopuffer_namespace_prefix: str = "bigrag_"

    redis_url: str = "redis://localhost:6379/0"

    master_key: str | None = None
    master_key_previous: list[str] = []

    session_expiry_hours: int = 168
    session_cookie_name: str = "bigrag_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_domain: str | None = None
    auth_principal_cache_ttl: int = 60
    allow_public_bind_in_prod: bool = False

    queue_max_depth: int = 10000
    collection_cache_ttl: int = 30
    query_embedding_cache_ttl: int = 300
    query_result_cache_ttl: int = 30
    embedding_cache_mode: Literal["encrypted", "disabled"] = "encrypted"
    embedding_cache_retention_days: int = 30
    conversion_timeout: int = 300
    conversion_pool_workers: int = max(1, (os.cpu_count() or 2) // 2)
    webhook_delivery_timeout: int = 10
    webhook_retry_delays: list[int] = [10, 30, 90]
    webhook_max_count: int = 50

    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    allowed_embedding_base_urls: list[str] = []
    allow_private_embedding_base_urls: bool = False
    allow_local_webhooks: bool = False

    chat_provider: str = "openai"
    chat_model: str = "gpt-4o-mini"
    chat_base_url: str | None = None
    chat_temperature: float = 0.2
    chat_max_context_chars: int = 120_000
    allowed_chat_base_urls: list[str] = []
    allow_private_chat_base_urls: bool = False

    upload_dir: str = "./data/uploads"
    backup_s3_bucket: str = ""
    backup_s3_endpoint_url: str | None = None
    backup_s3_region: str = "us-east-1"
    backup_s3_prefix: str = ""
    backup_s3_access_key_id: str | None = None
    backup_s3_secret_access_key: str | None = None
    backup_s3_force_path_style: bool = False

    max_upload_size_mb: int = 64
    max_batch_upload_size_mb: int = 128
    max_upload_session_files: int = 10000
    max_upload_session_size_mb: int = 102400
    upload_session_item_retention_hours: int = 168
    ingestion_workers: int = 4
    ingestion_batch_size: int = 128
    max_vector_upsert_count: int = 1000
    max_vector_delete_count: int = 10000
    max_vector_text_chars: int = 100000
    max_vector_metadata_bytes: int = 65536

    @classmethod
    def from_toml(cls, path: str | Path) -> Settings:
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, "rb") as f:
            data = tomllib.load(f)
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
        return cls(**flat)


settings = Settings()
