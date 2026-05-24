from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa

from bigrag.db.base import Base
from bigrag.db.engine import session_factory
from bigrag.services.backup.restore.coerce import _RESTORE_BATCH_SIZE, _coerce_row


async def _restore_tables(temp_dir: Path, objects: dict[str, str]) -> dict[str, int]:
    summary: dict[str, int] = {}
    ordered = list(Base.metadata.sorted_tables)
    mapper_by_table = {mapper.local_table.name: mapper for mapper in Base.registry.mappers}

    async with session_factory()() as session:
        for table in reversed(ordered):
            await session.execute(sa.delete(table))
        await session.commit()

    for table in ordered:
        path = f"postgres/tables/{table.name}.jsonl"
        if path not in objects:
            continue
        source = temp_dir / path
        if not source.exists():
            continue
        if table.name not in mapper_by_table:
            continue
        inserted = await _insert_table_rows(table, source)
        summary[table.name] = inserted
    return summary


async def _insert_table_rows(table: Any, source: Path) -> int:
    columns = {column.name: column for column in table.columns}
    inserted = 0
    batch: list[dict[str, Any]] = []
    async with session_factory()() as session:
        with source.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = orjson.loads(line)
                row = _coerce_row(table, columns, raw)
                batch.append(row)
                if len(batch) >= _RESTORE_BATCH_SIZE:
                    await session.execute(sa.insert(table).values(batch))
                    inserted += len(batch)
                    batch = []
            if batch:
                await session.execute(sa.insert(table).values(batch))
                inserted += len(batch)
        await session.commit()
    return inserted
