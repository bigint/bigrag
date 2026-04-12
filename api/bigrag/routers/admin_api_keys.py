"""Admin endpoints for creating and revoking API keys.

Plaintext keys are returned exactly once on creation. Only the prefix
and sha256 hash are persisted.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.database import build_update, db
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.auth import (
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UpdateApiKeyRequest,
)
from bigrag.models.common import StatusResponse
from bigrag.services.auth import generate_api_key

logger = get_logger("bigrag.routers.admin_api_keys")

router = APIRouter(prefix="/v1/admin/api-keys", tags=["admin:api-keys"])


def _row_to_response(row: dict) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=str(row["id"]),
        name=row["name"],
        prefix=row["prefix"],
        active=row["active"],
        last_used_at=row.get("last_used_at"),
        expires_at=row.get("expires_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
) -> ApiKeyListResponse:
    rows = await db.fetch(
        "SELECT * FROM api_keys ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    total = (await db.fetchrow("SELECT COUNT(*) AS cnt FROM api_keys"))["cnt"]
    return ApiKeyListResponse(keys=[_row_to_response(dict(r)) for r in rows], total=total)


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    admin: dict = Depends(require_session),
) -> CreateApiKeyResponse:
    plaintext, prefix, key_hash = generate_api_key()
    row = await db.fetchrow(
        """
        INSERT INTO api_keys (id, user_id, name, key_hash, prefix, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        uuid.uuid4(),
        uuid.UUID(admin["id"]),
        body.name,
        key_hash,
        prefix,
        body.expires_at,
    )
    logger.info(f"API key created: id={row['id']} name={body.name} by={admin['email']}")
    base = _row_to_response(dict(row))
    return CreateApiKeyResponse(**base.model_dump(), key=plaintext)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    body: UpdateApiKeyRequest,
    _: dict = Depends(require_session),
) -> ApiKeyResponse:
    try:
        target = uuid.UUID(key_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="API key not found") from e

    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.active is not None:
        fields["active"] = body.active

    if not fields:
        row = await db.fetchrow("SELECT * FROM api_keys WHERE id = $1", target)
        if not row:
            raise HTTPException(status_code=404, detail="API key not found")
        return _row_to_response(dict(row))

    sql, params = build_update("api_keys", fields, "id", target)
    row = await db.fetchrow(sql, *params)
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    return _row_to_response(dict(row))


@router.delete("/{key_id}", response_model=StatusResponse)
async def delete_api_key(
    key_id: str,
    admin: dict = Depends(require_session),
) -> StatusResponse:
    try:
        target = uuid.UUID(key_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="API key not found") from e

    row = await db.fetchrow("DELETE FROM api_keys WHERE id = $1 RETURNING id", target)
    if not row:
        raise HTTPException(status_code=404, detail="API key not found")
    logger.info(f"API key deleted: id={key_id} by={admin['email']}")
    return StatusResponse(status="ok", message="API key deleted")
