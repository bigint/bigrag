from __future__ import annotations

from typing import Any

from bigrag.logging import get_logger
from bigrag.services import runtime_settings
from bigrag.services.storage.base import StorageBackend
from bigrag.services.storage.local import LocalStorage
from bigrag.services.storage.s3 import S3Storage

logger = get_logger("bigrag.storage")

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Storage backend not initialized")
    return _storage


def init_storage(upload_dir: str = "./data/uploads") -> StorageBackend:
    global _storage

    _storage = LocalStorage(upload_dir)
    logger.info("local storage initialized", upload_dir=upload_dir)

    return _storage


async def init_storage_from_runtime(upload_dir: str = "./data/uploads") -> StorageBackend:
    values = await runtime_settings.all_runtime_values()
    return init_storage_from_values(upload_dir, values)


def init_storage_from_values(upload_dir: str, values: dict[str, Any]) -> StorageBackend:
    global _storage

    _storage = build_storage_from_values(upload_dir, values)
    if isinstance(_storage, LocalStorage):
        logger.info("local storage initialized", upload_dir=upload_dir)
    else:
        logger.info("s3 storage initialized", bucket=values.get("storage_s3_bucket"))
    return _storage


async def replace_storage_backend(backend: StorageBackend) -> StorageBackend:
    global _storage
    old = _storage
    _storage = backend
    if old is not None and old is not backend:
        try:
            await old.close()
        except Exception as exc:
            logger.warning("old storage close failed", error=str(exc))
    return _storage


def build_storage_from_values(upload_dir: str, values: dict[str, Any]) -> StorageBackend:
    backend = values.get("storage_backend") or "local"
    if backend == "local":
        return LocalStorage(upload_dir)
    if backend != "s3":
        raise ValueError(f"Unsupported storage backend: {backend}")
    return S3Storage(
        bucket=values.get("storage_s3_bucket") or "",
        endpoint_url=values.get("storage_s3_endpoint_url"),
        region=values.get("storage_s3_region") or "us-east-1",
        prefix=values.get("storage_s3_prefix") or "",
        access_key_id=values.get("storage_s3_access_key_id"),
        secret_access_key=values.get("storage_s3_secret_access_key"),
        force_path_style=bool(values.get("storage_s3_force_path_style")),
    )
