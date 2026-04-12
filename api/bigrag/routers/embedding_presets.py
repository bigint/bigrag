"""Admin endpoints for managing reusable embedding provider configs.

A preset bundles ``(provider, model, api_key, dimension, base_url?)`` under a
human-readable name so collections can reference it instead of duplicating keys.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import EmbeddingPreset
from bigrag.db.session import get_session
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


def _preset_response(preset: EmbeddingPreset) -> EmbeddingPresetResponse:
    return EmbeddingPresetResponse(
        id=str(preset.id),
        name=preset.name,
        provider=preset.provider,
        model=preset.model,
        base_url=preset.base_url,
        dimension=preset.dimension,
        has_api_key=bool(preset.api_key),
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


def _is_unique_violation(exc: IntegrityError) -> bool:
    return isinstance(exc.orig, UniqueViolationError) or "unique" in str(exc.orig).lower()


@router.get("", response_model=EmbeddingPresetListResponse)
async def list_presets(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> EmbeddingPresetListResponse:
    presets = (
        await session.scalars(
            sa.select(EmbeddingPreset)
            .order_by(EmbeddingPreset.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await session.scalar(sa.select(sa.func.count()).select_from(EmbeddingPreset))
    return EmbeddingPresetListResponse(
        presets=[_preset_response(p) for p in presets],
        total=total or 0,
    )


@router.post("", response_model=EmbeddingPresetResponse, status_code=201)
async def create_preset(
    body: CreateEmbeddingPresetRequest,
    admin: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> EmbeddingPresetResponse:
    preset = EmbeddingPreset(
        id=uuid.uuid4(),
        name=body.name,
        provider=body.provider,
        model=body.model,
        api_key=body.api_key,
        base_url=body.base_url,
        dimension=body.dimension,
    )
    session.add(preset)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if _is_unique_violation(e):
            raise HTTPException(
                status_code=409, detail="A preset with that name already exists"
            ) from e
        raise
    await session.refresh(preset)
    logger.info(f"Embedding preset created: name={body.name} by={admin['email']}")
    return _preset_response(preset)


@router.patch("/{preset_id}", response_model=EmbeddingPresetResponse)
async def update_preset(
    preset_id: str,
    body: UpdateEmbeddingPresetRequest,
    _: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> EmbeddingPresetResponse:
    try:
        target_id = uuid.UUID(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Preset not found") from e

    preset = await session.get(EmbeddingPreset, target_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    for col in ("name", "provider", "model", "api_key", "base_url", "dimension"):
        val = getattr(body, col)
        if val is not None:
            setattr(preset, col, val)

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if _is_unique_violation(e):
            raise HTTPException(
                status_code=409, detail="A preset with that name already exists"
            ) from e
        raise
    await session.refresh(preset)
    return _preset_response(preset)


@router.delete("/{preset_id}", response_model=StatusResponse)
async def delete_preset(
    preset_id: str,
    admin: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        target_id = uuid.UUID(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Preset not found") from e

    preset = await session.get(EmbeddingPreset, target_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    await session.delete(preset)
    await session.commit()

    logger.info(f"Embedding preset deleted: id={preset_id} by={admin['email']}")
    return StatusResponse(status="ok", message="Preset deleted")
