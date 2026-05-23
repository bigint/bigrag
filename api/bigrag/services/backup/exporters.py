from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa

from bigrag.db.base import Base
from bigrag.db.engine import session_factory
from bigrag.db.models import Collection, EmbeddingCache
from bigrag.services.vector_store import vector_store

from .constants import _SENSITIVE_COLUMN_NAMES, REDACTED
from .filesystem import _readable_value, _write_json


async def _export_tables(temp_dir: Path) -> dict[str, int]:
    out_dir = temp_dir / "postgres" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    async with session_factory()() as session:
        await session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        for mapper in sorted(Base.registry.mappers, key=lambda item: item.local_table.name):
            model = mapper.class_
            table_name = mapper.local_table.name
            count = 0
            target = out_dir / f"{table_name}.jsonl"
            result = await session.stream_scalars(sa.select(model))
            with target.open("wb") as f:
                async for row in result:
                    f.write(orjson.dumps(_row_payload(row, mapper)) + b"\n")
                    count += 1
            counts[table_name] = count
    return counts


def _row_payload(row: Any, mapper: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        column = attr.columns[0]
        value = getattr(row, attr.key)
        if _redact_column(row, column):
            payload[column.name] = REDACTED if value is not None else None
        elif isinstance(row, EmbeddingCache) and column.name == "vector":
            payload[column.name] = REDACTED
        else:
            payload[column.name] = _readable_value(value)
    return payload


def _redact_column(row: Any, column: Any) -> bool:
    if column.name in _SENSITIVE_COLUMN_NAMES:
        return True
    if isinstance(row, EmbeddingCache) and column.name == "vector":
        return True
    return column.type.__class__.__name__ == "EncryptedString"


async def _export_vector_store(temp_dir: Path) -> dict[str, int]:
    points_dir = temp_dir / "vector_store" / "points"
    points_dir.mkdir(parents=True, exist_ok=True)
    collections_meta = []
    counts: dict[str, int] = {}
    async with session_factory()() as session:
        collections = (
            await session.scalars(sa.select(Collection).order_by(Collection.name.asc()))
        ).all()
    for collection in collections:
        count = 0
        target = points_dir / f"{collection.name}.jsonl"
        with target.open("wb") as f:
            async for point in vector_store.iter_collection_points(
                collection.name,
                with_vectors=False,
            ):
                f.write(orjson.dumps(_point_payload(point)) + b"\n")
                count += 1
        exists = count > 0 or collection.document_count == 0
        if not exists and collection.document_count > 0:
            raise RuntimeError(f"Vector store collection missing: {collection.name}")
        counts[collection.name] = count
        collections_meta.append(
            {
                "collection": collection.name,
                "vector_store_collection": collection.name,
                "exists": exists,
                "points": count,
            }
        )
    _write_json(temp_dir / "vector_store" / "collections.json", collections_meta)
    return counts


def _point_payload(point: Any) -> dict[str, Any]:
    if isinstance(point, dict):
        return {
            "id": str(point.get("id", "")),
            "payload": _readable_value(point.get("payload") or {}),
            "vector": REDACTED,
        }
    return {
        "id": str(getattr(point, "id", "")),
        "payload": _readable_value(getattr(point, "payload", {}) or {}),
        "vector": REDACTED,
    }
