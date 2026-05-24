from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.storage import get_storage


@dataclass(frozen=True)
class StagedDocument:
    path: str
    suffix: str
    bytes_written: int


async def stage_document(job: IngestionJob) -> StagedDocument:
    suffix = Path(job.file_path).suffix.lower()

    def make_tmp() -> str:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        return tmp.name

    tmp_path = await asyncio.to_thread(make_tmp)
    bytes_written = 0
    storage = get_storage()

    try:

        def open_write():
            return open(tmp_path, "wb")

        fh = await asyncio.to_thread(open_write)
        try:
            async for chunk in storage.get_stream(job.file_path):
                await asyncio.to_thread(fh.write, chunk)
                bytes_written += len(chunk)
        finally:
            await asyncio.to_thread(fh.close)
    except BaseException:
        await remove_staged_document(tmp_path)
        raise

    return StagedDocument(path=tmp_path, suffix=suffix, bytes_written=bytes_written)


async def remove_staged_document(path: str) -> None:
    await asyncio.to_thread(Path(path).unlink, True)
