from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO


class StorageBackend(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def put_stream(self, key: str, fileobj: BinaryIO, size: int | None = None) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def get_stream(self, key: str, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        if False:
            yield b""

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def write_to_path(self, key: str, path: Path) -> int: ...

    @abstractmethod
    async def close(self) -> None: ...
