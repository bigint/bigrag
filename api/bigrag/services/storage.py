from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from bigrag.logging import get_logger

logger = get_logger("bigrag.storage")


class StorageBackend(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:

        resolved = (self._base / key).resolve()
        if resolved != self._base and self._base not in resolved.parents:
            raise ValueError(f"Invalid storage key: {key}")
        return resolved

    async def put(self, key: str, data: bytes) -> None:
        path = self._safe_path(key)

        def _write():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        logger.info(f"local put: key={key} size={len(data)}")

    async def get(self, key: str) -> bytes:
        path = self._safe_path(key)

        def _read():
            if not path.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return path.read_bytes()

        data = await asyncio.to_thread(_read)
        logger.info(f"local get: key={key} size={len(data)}")
        return data

    async def delete(self, key: str) -> None:
        path = self._safe_path(key)

        def _delete():
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_delete)
        logger.info(f"local delete: key={key}")

    async def delete_prefix(self, prefix: str) -> int:
        import shutil

        target = self._safe_path(prefix)

        def _delete_prefix():
            if not target.exists():
                return 0
            if target.is_dir():
                count = sum(1 for _ in target.rglob("*") if _.is_file())
                shutil.rmtree(target, ignore_errors=True)
                return count
            target.unlink()
            return 1

        count = await asyncio.to_thread(_delete_prefix)
        if count:
            logger.info(f"local delete_prefix: prefix={prefix} count={count}")
        return count

    async def exists(self, key: str) -> bool:
        path = self._safe_path(key)
        return await asyncio.to_thread(path.exists)

    async def close(self) -> None:
        pass


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Storage backend not initialized")
    return _storage


def init_storage(upload_dir: str = "./data/uploads") -> StorageBackend:
    global _storage

    _storage = LocalStorage(upload_dir)
    logger.info(f"Local storage initialized dir={upload_dir}")

    return _storage
