from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Document


def result_to_dict(row: dict, *, include_multimodal: bool) -> dict:
    cleaned = {k: v for k, v in row.items() if k != "embedding"}
    metadata = cleaned.get("metadata") or {}
    for field_name in ("page_no", "char_start", "char_end", "document_filename"):
        if field_name in metadata and field_name not in cleaned:
            cleaned[field_name] = metadata[field_name]
    if (
        include_multimodal
        and "multimodal_elements" in metadata
        and "multimodal_elements" not in cleaned
    ):
        cleaned["multimodal_elements"] = metadata["multimodal_elements"]
    if not include_multimodal and isinstance(metadata, dict):
        cleaned["metadata"] = {k: v for k, v in metadata.items() if k != "multimodal_elements"}
    return cleaned


async def results_with_document_filenames(rows: list[dict]) -> list[dict]:
    document_ids = []
    for row in rows:
        if row.get("document_filename"):
            continue
        raw = row.get("document_id")
        if raw is None:
            continue
        try:
            document_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not document_ids:
        return rows
    async with session_factory()() as session:
        records = await session.execute(
            sa.select(Document.id, Document.filename).where(Document.id.in_(set(document_ids)))
        )
        filenames = {str(document_id): filename for document_id, filename in records.all()}
    return [
        {
            **row,
            "document_filename": row.get("document_filename")
            or filenames.get(str(row.get("document_id"))),
        }
        for row in rows
    ]
