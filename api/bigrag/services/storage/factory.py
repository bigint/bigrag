from __future__ import annotations

from bigrag.logging import get_logger
from bigrag.services.storage.base import StorageBackend
from bigrag.services.storage.local import LocalStorage

logger = get_logger("bigrag.storage")

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Ingestion staging backend not initialized")
    return _storage


def init_storage(upload_dir: str = "./data/uploads") -> StorageBackend:
    global _storage

    _storage = LocalStorage(upload_dir)
    logger.info("local storage initialized", upload_dir=upload_dir)

    return _storage


async def init_storage_from_runtime(upload_dir: str = "./data/uploads") -> StorageBackend:
    return init_storage(upload_dir)
