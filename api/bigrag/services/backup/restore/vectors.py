from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson

from bigrag.services.backup.constants import REDACTED
from bigrag.services.backup.restore.coerce import _RESTORE_BATCH_SIZE, RestoreRedactedError
from bigrag.services.vector_store import vector_store


async def _restore_vectors(
    temp_dir: Path,
    objects: dict[str, str],
    *,
    restore_vectors: bool,
) -> dict[str, Any]:
    collections_path = "vector_store/collections.json"
    if collections_path not in objects:
        return {"restored": False, "reason": "no vector_store metadata in backup"}
    collections = orjson.loads((temp_dir / collections_path).read_bytes())

    summary: dict[str, Any] = {"collections": {}, "restored": True}
    for entry in collections:
        name = entry.get("collection") or entry.get("vector_store_collection")
        if not name:
            continue
        dimension = entry.get("dimension")
        points_path = f"vector_store/points/{name}.jsonl"
        source = temp_dir / points_path
        point_count = await _restore_collection_points(
            name,
            dimension,
            source if points_path in objects and source.exists() else None,
            restore_vectors=restore_vectors,
        )
        summary["collections"][name] = point_count
    return summary


async def _restore_collection_points(
    name: str,
    dimension: int | None,
    source: Path | None,
    *,
    restore_vectors: bool,
) -> dict[str, Any]:
    if dimension:
        await vector_store.create_collection(name, dimension)

    if source is None:
        return {"namespace_created": bool(dimension), "points": 0, "vectors_inserted": False}

    has_vectors, total = _scan_points(source)
    if total == 0:
        return {"namespace_created": bool(dimension), "points": 0, "vectors_inserted": False}

    if not has_vectors:
        if restore_vectors:
            raise RestoreRedactedError(
                f"Collection {name} points have redacted vectors; cannot re-embed during restore"
            )
        return {
            "namespace_created": bool(dimension),
            "points": total,
            "vectors_inserted": False,
            "warning": "vectors redacted in backup; points not re-inserted",
        }

    inserted = await _insert_points(name, source)
    return {
        "namespace_created": bool(dimension),
        "points": total,
        "vectors_inserted": True,
        "inserted": inserted,
    }


def _scan_points(source: Path) -> tuple[bool, int]:
    has_vectors = True
    total = 0
    with source.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = orjson.loads(line)
            vector = record.get("vector")
            if vector == REDACTED or vector is None:
                has_vectors = False
    return has_vectors, total


async def _insert_points(name: str, source: Path) -> int:
    inserted = 0
    ids: list[str] = []
    document_ids: list[str] = []
    chunk_indices: list[int] = []
    texts: list[str] = []
    embeddings: list[list[float]] = []
    metadata: list[dict] = []

    async def flush() -> int:
        if not ids:
            return 0
        count = await vector_store.insert(
            name,
            list(ids),
            list(document_ids),
            list(chunk_indices),
            list(texts),
            list(embeddings),
            list(metadata),
        )
        ids.clear()
        document_ids.clear()
        chunk_indices.clear()
        texts.clear()
        embeddings.clear()
        metadata.clear()
        return count

    with source.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = orjson.loads(line)
            payload = record.get("payload") or {}
            public_id = payload.get("id") or record.get("id")
            ids.append(str(public_id))
            document_ids.append(str(payload.get("document_id") or ""))
            chunk_indices.append(int(payload.get("chunk_index") or 0))
            texts.append(str(payload.get("text") or ""))
            embeddings.append([float(component) for component in record.get("vector") or []])
            metadata.append(
                {
                    k: v
                    for k, v in payload.items()
                    if k not in {"id", "document_id", "chunk_index", "text"}
                }
            )
            if len(ids) >= _RESTORE_BATCH_SIZE:
                inserted += await flush()
    inserted += await flush()
    return inserted
