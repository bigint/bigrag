from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ApiKey
from bigrag.db.session import get_session
from bigrag.exceptions import ValidationError
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import invalidate_api_key_principal, require_admin_session
from bigrag.models import StatusResponse
from bigrag.models.auth import (
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UpdateApiKeyRequest,
)
from bigrag.routers import uuid_or_404, validate_collection_name
from bigrag.services import audit
from bigrag.services.auth import generate_api_key
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor

logger = get_logger("bigrag.routers.admin_api_keys")

router = APIRouter(prefix="/v1/admin/api-keys", tags=["admin:api-keys"])


def _mcp_permissions_filter():
    return ApiKey.permissions.op("?")("mcp")


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

    permissions = key.permissions or {}
    return isinstance(permissions, dict) and isinstance(permissions.get("mcp"), dict)


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyListResponse:
    cursor_tuple = None
    if cursor:
        try:
            cursor_tuple = decode_cursor(cursor)
        except ValidationError as exc:
            raise HTTPException(
                status_code=400, detail=safe_error_detail(exc, "Invalid cursor.")
            ) from exc

    base = sa.select(ApiKey).where(sa.not_(_mcp_permissions_filter()))
    stmt = base.order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
    if cursor_tuple is not None:
        stmt = apply_cursor(stmt, ApiKey.created_at, ApiKey.id, cursor_tuple).limit(limit + 1)
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(ApiKey)
                .where(sa.not_(_mcp_permissions_filter()))
            )
        ) or 0
    return ApiKeyListResponse(
        keys=[_key_response(k) for k in page],
        total=total,
        next_cursor=next_cursor,
    )


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> CreateApiKeyResponse:
    try:
        _validate_scopes(body.scopes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=safe_error_detail(e, "Invalid scopes.")) from e

    collection = await validate_collection_name(session, body.collection)
    permissions: dict = {}
    if body.scopes:
        permissions["scopes"] = body.scopes
    if collection:
        permissions["collection"] = collection
    plaintext, prefix, key_hash = generate_api_key()
    key = ApiKey(
        id=uuid7(),
        user_id=uuid.UUID(admin["id"]),
        name=body.name,
        key_hash=key_hash,
        prefix=prefix,
        expires_at=body.expires_at,
        permissions=permissions,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)

    logger.info("api key created", id=str(key.id), name=body.name, actor=admin["email"])
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
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyResponse:
    target_id = uuid_or_404(key_id, "API key")

    key = await session.get(ApiKey, target_id)
    if key is None or _is_mcp_key(key):
        raise HTTPException(status_code=404, detail="API key not found")
    previous_hash = key.key_hash

    fields: list[str] = []
    if body.name is not None:
        key.name = body.name
        fields.append("name")
    if body.active is not None:
        key.active = body.active
        fields.append("active")
    if body.expires_at is not None:
        key.expires_at = body.expires_at
        fields.append("expires_at")
    existing = dict(key.permissions or {})
    if body.scopes is not None:
        try:
            _validate_scopes(body.scopes)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=safe_error_detail(e, "Invalid scopes.")
            ) from e
        if body.scopes:
            existing["scopes"] = body.scopes
        else:
            existing.pop("scopes", None)
        fields.append("scopes")
    if body.collection is not None:
        collection = await validate_collection_name(session, body.collection)
        if collection:
            existing["collection"] = collection
        else:
            existing.pop("collection", None)
        fields.append("collection")
    if body.scopes is not None or body.collection is not None:
        key.permissions = existing

    await session.commit()
    await session.refresh(key)
    await invalidate_api_key_principal(previous_hash)
    audit.record(
        request,
        user=admin,
        action="api_key.update",
        resource_type="api_key",
        resource_id=str(key.id),
        metadata={"name": key.name, "fields": fields},
    )
    return _key_response(key)


@router.post("/{key_id}/rotate", response_model=CreateApiKeyResponse)
async def rotate_api_key(
    key_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> CreateApiKeyResponse:
    target_id = uuid_or_404(key_id, "API key")

    key = await session.get(ApiKey, target_id)
    if key is None or _is_mcp_key(key):
        raise HTTPException(status_code=404, detail="API key not found")
    previous_hash = key.key_hash
    plaintext, prefix, key_hash = generate_api_key()
    key.key_hash = key_hash
    key.prefix = prefix
    key.last_used_at = None
    key.active = True
    await session.commit()
    await session.refresh(key)
    await invalidate_api_key_principal(previous_hash)
    audit.record(
        request,
        user=admin,
        action="api_key.rotate",
        resource_type="api_key",
        resource_id=str(key.id),
        metadata={"name": key.name},
    )
    base = _key_response(key)
    return CreateApiKeyResponse(**base.model_dump(), key=plaintext)


@router.delete("/{key_id}", response_model=StatusResponse)
async def delete_api_key(
    key_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    target_id = uuid_or_404(key_id, "API key")

    key = await session.get(ApiKey, target_id)
    if key is None or _is_mcp_key(key):
        raise HTTPException(status_code=404, detail="API key not found")
    deleted_name = key.name
    deleted_hash = key.key_hash
    await session.delete(key)
    await session.commit()
    await invalidate_api_key_principal(deleted_hash)

    logger.info("api key deleted", id=key_id, actor=admin["email"])
    audit.record(
        request,
        user=admin,
        action="api_key.delete",
        resource_type="api_key",
        resource_id=key_id,
        metadata={"name": deleted_name},
    )
    return StatusResponse(status="ok", message="API key deleted")
