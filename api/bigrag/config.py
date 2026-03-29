from __future__ import annotations

import tomli
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BIGRAG_", env_nested_delimiter="__")

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    log_level: str = "info"
    log_format: str = "text"
    cors_origins: list[str] = ["*"]

    # Postgres
    database_url: str = "postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
    db_pool_min: int = 5
    db_pool_max: int = 50

    # Milvus
    milvus_uri: str = "http://localhost:19530"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    master_key: str | None = None
    jwt_secret: str | None = None
    api_keys: list[str] = []
    session_expiry_hours: int = 168

    # Embedding defaults
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None

    # Ingestion
    chunk_size: int = 512
    chunk_overlap: int = 50
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 500
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
