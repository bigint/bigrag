from __future__ import annotations

from bigrag.logging import get_logger
from bigrag.services.storage.base import StorageBackend
from bigrag.services.storage.local import LocalStorage
from bigrag.services.storage.s3 import S3Storage

logger = get_logger("bigrag.storage")

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Ingestion staging backend not initialized")
    return _storage


def _build_s3_storage() -> S3Storage:
    from bigrag.config import settings

    return S3Storage(
        bucket=settings.storage_s3_bucket,
        prefix=settings.storage_s3_prefix,
        endpoint_url=settings.storage_s3_endpoint_url,
        region=settings.storage_s3_region,
        access_key_id=settings.storage_s3_access_key_id,
        secret_access_key=settings.storage_s3_secret_access_key,
        force_path_style=settings.storage_s3_force_path_style,
    )


def init_storage(upload_dir: str = "./data/uploads") -> StorageBackend:
    global _storage

    backend = "local"
    try:
        from bigrag.config import settings

        backend = settings.storage_backend
    except Exception:
        backend = "local"

    if backend == "s3":
        _storage = _build_s3_storage()
        logger.info("s3 storage initialized")
    else:
        _storage = LocalStorage(upload_dir)
        logger.info("local storage initialized", upload_dir=upload_dir)

    return _storage


async def init_storage_from_runtime(upload_dir: str = "./data/uploads") -> StorageBackend:
    return init_storage(upload_dir)
