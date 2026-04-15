"""Admin endpoints for creating and revoking API keys.

Plaintext keys are returned exactly once on creation. Only the prefix
and sha256 hash are persisted.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ApiKey, Collection
from bigrag.db.session import get_session
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
from bigrag.services import audit
from bigrag.services.auth import generate_api_key

logger = get_logger("bigrag.routers.admin_api_keys")

router = APIRouter(prefix="/v1/admin/api-keys", tags=["admin:api-keys"])


def _key_response(key: ApiKey) -> ApiKeyResponse:
    permissions = key.permissions or {}
    scopes = permissions.get("scopes") if isinstance(permissions, dict) else None
    raw_collection = permissions.get("collection") if isinstance(permissions, dict) else None
    collection = raw_collection if isinstance(raw_collection, str) and raw_collection else None
    return ApiKeyResponse(
        id=str(key.id),
        name=key.name,
        prefix=key.prefix,
        active=key.active,
        scopes=scopes if isinstance(scopes, list) else [],
        collection=collection,
        rate_limits=key.rate_limits or None,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


def _validate_scopes(scopes: list[str] | None) -> None:
    if not scopes:
        return
    from bigrag.services.scopes import validate_scope_string

    for s in scopes:
        validate_scope_string(s)


def _is_mcp_key(key: ApiKey) -> bool:
    """MCP-server keys live in the same table but are managed from
    ``/v1/admin/mcp-servers``. Hide them from generic api-keys CRUD."""
    permissions = key.permissions or {}
    return isinstance(permissions, dict) and isinstance(permissions.get("mcp"), dict)


async def _validate_collection(session: AsyncSession, collection: str | None) -> str | None:
    """Return the normalized collection name or None. Raises 400 if the
    name is provided but doesn't match an existing collection."""
    if collection is None:
        return None
    name = collection.strip()
    if not name:
        return None
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=400, detail=f"Collection {name!r} does not exist")
    return name


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyListResponse:
    # Keys minted by the /mcp page live in the same table; filter them
    # out here so they're only visible from their own admin UI.
    base = sa.select(ApiKey).where(ApiKey.permissions["mcp"].is_(None))
    keys = (
        await session.scalars(base.order_by(ApiKey.created_at.desc()).limit(limit).offset(offset))
    ).all()
    total = await session.scalar(
        sa.select(sa.func.count()).select_from(ApiKey).where(ApiKey.permissions["mcp"].is_(None))
    )
    return ApiKeyListResponse(keys=[_key_response(k) for k in keys], total=total or 0)


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    request: Request,
    admin: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> CreateApiKeyResponse:
    try:
        _validate_scopes(body.scopes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    collection = await _validate_collection(session, body.collection)
    permissions: dict = {}
    if body.scopes:
        permissions["scopes"] = body.scopes
    if collection:
        permissions["collection"] = collection
    plaintext, prefix, key_hash = generate_api_key()
    key = ApiKey(
        id=uuid.uuid4(),
        user_id=uuid.UUID(admin["id"]),
        name=body.name,
        key_hash=key_hash,
        prefix=prefix,
        expires_at=body.expires_at,
        permissions=permissions,
        rate_limits=body.rate_limits or {},
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)

    logger.info(f"API key created: id={key.id} name={body.name} by={admin['email']}")
    audit.record(
        request,
        user=admin,
        action="api_key.create",
        resource_type="api_key",
        resource_id=str(key.id),
        metadata={
            "name": body.name,
            "scopes": body.scopes or [],
            "collection": collection,
        },
    )
    base = _key_response(key)
    return CreateApiKeyResponse(**base.model_dump(), key=plaintext)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    body: UpdateApiKeyRequest,
    _: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyResponse:
    try:
        target_id = uuid.UUID(key_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="API key not found") from e

    key = await session.get(ApiKey, target_id)
    if key is None or _is_mcp_key(key):
        raise HTTPException(status_code=404, detail="API key not found")

    if body.name is not None:
        key.name = body.name
    if body.active is not None:
        key.active = body.active
    existing = dict(key.permissions or {})
    if body.scopes is not None:
        try:
            _validate_scopes(body.scopes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if body.scopes:
            existing["scopes"] = body.scopes
        else:
            existing.pop("scopes", None)
    if body.collection is not None:
        collection = await _validate_collection(session, body.collection)
        if collection:
            existing["collection"] = collection
        else:
            existing.pop("collection", None)
    if body.scopes is not None or body.collection is not None:
        key.permissions = existing
    if body.rate_limits is not None:
        key.rate_limits = body.rate_limits

    await session.commit()
    await session.refresh(key)
    return _key_response(key)


@router.delete("/{key_id}", response_model=StatusResponse)
async def delete_api_key(
    key_id: str,
    admin: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        target_id = uuid.UUID(key_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="API key not found") from e

    key = await session.get(ApiKey, target_id)
    if key is None or _is_mcp_key(key):
        raise HTTPException(status_code=404, detail="API key not found")
    await session.delete(key)
    await session.commit()

    logger.info(f"API key deleted: id={key_id} by={admin['email']}")
    return StatusResponse(status="ok", message="API key deleted")
