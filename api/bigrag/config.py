from __future__ import annotations

from pathlib import Path

import tomli
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIGRAG_", env_nested_delimiter="__")

    # Deployment mode. ``prod`` enables startup safety checks (see
    # bigrag.main.lifespan); ``dev`` skips them. Values outside this
    # enum fall through as ``dev``.
    env: str = "dev"

    # Server
    host: str = "0.0.0.0"
    port: int = 6100
    workers: int = 4
    log_level: str = "info"
    log_format: str = "text"
    cors_origins: list[str] = []

    # Postgres
    database_url: str = "postgres://bigrag:bigrag@localhost:5433/bigrag?sslmode=disable"
    db_pool_min: int = 5
    db_pool_max: int = 50

    # Milvus
    milvus_uri: str = "http://localhost:19530"

    # Redis
    redis_url: str = "redis://localhost:6380/0"

    # Auth
    session_expiry_hours: int = 168
    session_cookie_name: str = "bigrag_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_cookie_domain: str | None = None

    # Tuning
    embedding_concurrency: int = 8
    milvus_max_workers: int = 32
    milvus_nprobe: int = 32
    collection_cache_ttl: int = 30
    queue_max_depth: int = 10000
    conversion_timeout: int = 300
    webhook_delivery_timeout: int = 10
    webhook_retry_delays: list[int] = [10, 30, 90]
    webhook_cache_ttl: int = 60

    # Embedding defaults
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_api_key: str | None = None

    # Storage
    storage_backend: str = "local"
    upload_dir: str = "./data/uploads"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # Ingestion
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_upload_size_mb: int = 1024
    ingestion_workers: int = 4
    ingestion_batch_size: int = 128

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
                    flat[f"{section}_{k}"] = v
            else:
                flat[section] = values
        return cls(**flat)


settings = Settings()
