"""Admin endpoints for managing reusable embedding provider configs.

A preset bundles ``(provider, model, api_key, dimension, base_url?)`` under a
human-readable name so collections can reference it instead of duplicating keys.
"""

from __future__ import annotations

import uuid

from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.database import build_update, db
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.common import StatusResponse
from bigrag.models.embedding_preset import (
    CreateEmbeddingPresetRequest,
    EmbeddingPresetListResponse,
    EmbeddingPresetResponse,
    UpdateEmbeddingPresetRequest,
)

logger = get_logger("bigrag.routers.embedding_presets")

router = APIRouter(prefix="/v1/admin/embedding-presets", tags=["admin:embedding-presets"])


def _row_to_response(row: dict) -> EmbeddingPresetResponse:
    return EmbeddingPresetResponse(
        id=str(row["id"]),
        name=row["name"],
        provider=row["provider"],
        model=row["model"],
        base_url=row.get("base_url"),
        dimension=row["dimension"],
        has_api_key=bool(row.get("api_key")),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=EmbeddingPresetListResponse)
async def list_presets(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
) -> EmbeddingPresetListResponse:
    rows = await db.fetch(
        "SELECT * FROM embedding_presets ORDER BY created_at ASC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    total = (await db.fetchrow("SELECT COUNT(*) AS cnt FROM embedding_presets"))["cnt"]
    return EmbeddingPresetListResponse(
        presets=[_row_to_response(dict(r)) for r in rows],
        total=total,
    )


@router.post("", response_model=EmbeddingPresetResponse, status_code=201)
async def create_preset(
    body: CreateEmbeddingPresetRequest,
    admin: dict = Depends(require_session),
) -> EmbeddingPresetResponse:
    try:
        row = await db.fetchrow(
            """
            INSERT INTO embedding_presets
                (id, name, provider, model, api_key, base_url, dimension)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            uuid.uuid4(),
            body.name,
            body.provider,
            body.model,
            body.api_key,
            body.base_url,
            body.dimension,
        )
    except UniqueViolationError as e:
        raise HTTPException(status_code=409, detail="A preset with that name already exists") from e
    logger.info(f"Embedding preset created: name={body.name} by={admin['email']}")
    return _row_to_response(dict(row))


@router.patch("/{preset_id}", response_model=EmbeddingPresetResponse)
async def update_preset(
    preset_id: str,
    body: UpdateEmbeddingPresetRequest,
    _: dict = Depends(require_session),
) -> EmbeddingPresetResponse:
    try:
        target = uuid.UUID(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Preset not found") from e

    fields: dict = {}
    for col in ("name", "provider", "model", "api_key", "base_url", "dimension"):
        val = getattr(body, col)
        if val is not None:
            fields[col] = val

    if not fields:
        row = await db.fetchrow("SELECT * FROM embedding_presets WHERE id = $1", target)
        if not row:
            raise HTTPException(status_code=404, detail="Preset not found")
        return _row_to_response(dict(row))

    sql, params = build_update("embedding_presets", fields, "id", target)
    try:
        row = await db.fetchrow(sql, *params)
    except UniqueViolationError as e:
        raise HTTPException(status_code=409, detail="A preset with that name already exists") from e
    if not row:
        raise HTTPException(status_code=404, detail="Preset not found")
    return _row_to_response(dict(row))


@router.delete("/{preset_id}", response_model=StatusResponse)
async def delete_preset(
    preset_id: str,
    admin: dict = Depends(require_session),
) -> StatusResponse:
    try:
        target = uuid.UUID(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Preset not found") from e

    row = await db.fetchrow(
        "DELETE FROM embedding_presets WHERE id = $1 RETURNING id",
        target,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preset not found")
    logger.info(f"Embedding preset deleted: id={preset_id} by={admin['email']}")
    return StatusResponse(status="ok", message="Preset deleted")
