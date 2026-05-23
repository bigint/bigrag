from __future__ import annotations

import asyncio
import io
import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

from bigrag.logging import get_logger
from bigrag.services.storage.base import StorageBackend

logger = get_logger("bigrag.storage")


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
        await self.put_stream(key, io.BytesIO(data), size=len(data))

    async def put_stream(self, key: str, fileobj: BinaryIO, size: int | None = None) -> None:
        path = self._safe_path(key)
        tmp = path.with_suffix(path.suffix + ".tmp")

        def _write() -> int:
            path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with tmp.open("wb") as out:
                shutil.copyfileobj(fileobj, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
                written = out.tell()
            os.replace(tmp, path)
            return written

        try:
            written = await asyncio.to_thread(_write)
        except BaseException:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise
        logger.info("local put", key=key, size=size if size is not None else written)

    async def get(self, key: str) -> bytes:
        path = self._safe_path(key)

        def _read():
            if not path.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return path.read_bytes()

        data = await asyncio.to_thread(_read)
        logger.info("local get", key=key, size=len(data))
        return data

    async def get_stream(self, key: str, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        path = self._safe_path(key)

        def _open():
            if not path.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return path.open("rb")

        fh = await asyncio.to_thread(_open)
        try:
            while True:
                chunk = await asyncio.to_thread(fh.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(fh.close)

    async def delete(self, key: str) -> None:
        path = self._safe_path(key)

        def _delete():
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_delete)
        logger.info("local delete", key=key)

    async def delete_prefix(self, prefix: str) -> int:
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
            logger.info("local delete_prefix", prefix=prefix, count=count)
        return count

    async def exists(self, key: str) -> bool:
        path = self._safe_path(key)
        return await asyncio.to_thread(path.exists)

    async def close(self) -> None:
        pass
