from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ApiKey, Collection
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import invalidate_api_key_principal, require_admin_session
from bigrag.models.common import StatusResponse
from bigrag.services import audit
from bigrag.services.auth import generate_api_key

logger = get_logger("bigrag.routers.mcp_servers")

router = APIRouter(prefix="/v1/admin/mcp-servers", tags=["admin:mcp-servers"])


class McpServerBase(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    server_name: str = Field(
        min_length=1,
        max_length=60,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
        description="mcpServers object key in the client config; lowercase, alphanumeric + dashes.",
    )
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Optional collection to pin the server to.",
    )


class CreateMcpServerRequest(McpServerBase):
    pass


class UpdateMcpServerRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    server_name: str | None = Field(
        default=None, min_length=1, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$"
    )
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Empty string clears the scope; a name pins to that collection.",
    )


class McpServerResponse(BaseModel):
    id: str
    title: str
    server_name: str
    collection: str | None = None
    key_prefix: str
    key_active: bool
    last_used_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateMcpServerResponse(McpServerResponse):
    api_key: str = Field(description="Plaintext API key — shown once.")


class McpServerListResponse(BaseModel):
    servers: list[McpServerResponse]
    total: int


def _to_response(key: ApiKey) -> McpServerResponse:
    permissions = key.permissions or {}
    mcp = permissions.get("mcp") or {}
    raw_collection = permissions.get("collection")
    collection = raw_collection if isinstance(raw_collection, str) and raw_collection else None
    return McpServerResponse(
        id=str(key.id),
        title=mcp.get("title") or key.name,
        server_name=mcp.get("server_name") or "bigrag",
        collection=collection,
        key_prefix=key.prefix,
        key_active=key.active,
        last_used_at=key.last_used_at,
        created_at=key.created_at,
        updated_at=key.updated_at,
    )


def _permissions(title: str, server_name: str, collection: str | None) -> dict:
    permissions: dict = {"mcp": {"title": title, "server_name": server_name}}
    if collection:
        permissions["collection"] = collection
    return permissions


async def _validate_collection(session: AsyncSession, collection: str | None) -> str | None:
    if collection is None:
        return None
    name = collection.strip()
    if not name:
        return None
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=400, detail=f"Collection {name!r} does not exist")
    return name


async def _server_name_conflict(
    session: AsyncSession,
    user_id: uuid.UUID,
    server_name: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:

    q = sa.select(ApiKey).where(
        ApiKey.user_id == user_id,
        ApiKey.permissions["mcp"]["server_name"].astext == server_name,
    )
    if exclude_id is not None:
        q = q.where(ApiKey.id != exclude_id)
    existing = await session.scalar(q)
    return existing is not None


def _is_mcp(key: ApiKey | None) -> bool:
    if key is None:
        return False
    permissions = key.permissions or {}
    return isinstance(permissions, dict) and isinstance(permissions.get("mcp"), dict)


@router.get("", response_model=McpServerListResponse)
async def list_mcp_servers(
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> McpServerListResponse:
    user_id = uuid.UUID(admin["id"])
    rows = (
        await session.scalars(
            sa.select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .where(ApiKey.permissions["mcp"].is_not(None))
            .order_by(ApiKey.created_at.desc())
        )
    ).all()
    return McpServerListResponse(
        servers=[_to_response(k) for k in rows],
        total=len(rows),
    )


@router.post("", response_model=CreateMcpServerResponse, status_code=201)
async def create_mcp_server(
    body: CreateMcpServerRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> CreateMcpServerResponse:
    user_id = uuid.UUID(admin["id"])
    if await _server_name_conflict(session, user_id, body.server_name):
        raise HTTPException(
            status_code=409,
            detail=f"An MCP server named {body.server_name!r} already exists.",
        )
    collection = await _validate_collection(session, body.collection)
    plaintext, prefix, key_hash = generate_api_key()
    key = ApiKey(
        id=uuid.uuid4(),
        user_id=user_id,
        name=f"mcp:{body.server_name}",
        key_hash=key_hash,
        prefix=prefix,
        permissions=_permissions(body.title, body.server_name, collection),
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)

    logger.info(
        "mcp server created",
        id=str(key.id),
        server_name=body.server_name,
        collection=collection,
        actor=admin["email"],
    )
    audit.record(
        request,
        user=admin,
        action="mcp_server.create",
        resource_type="mcp_server",
        resource_id=str(key.id),
        metadata={
            "title": body.title,
            "server_name": body.server_name,
            "collection": collection,
        },
    )

    base = _to_response(key)
    return CreateMcpServerResponse(**base.model_dump(), api_key=plaintext)


@router.patch("/{server_id}", response_model=McpServerResponse)
async def update_mcp_server(
    server_id: str,
    body: UpdateMcpServerRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> McpServerResponse:
    try:
        target_id = uuid.UUID(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="MCP server not found") from e

    key = await session.get(ApiKey, target_id)
    if not _is_mcp(key) or key.user_id != uuid.UUID(admin["id"]):
        raise HTTPException(status_code=404, detail="MCP server not found")
    previous_hash = key.key_hash

    permissions = dict(key.permissions or {})
    mcp = dict(permissions.get("mcp") or {})
    fields: list[str] = []

    if body.title is not None:
        mcp["title"] = body.title
        fields.append("title")
    if body.server_name is not None:
        if await _server_name_conflict(
            session,
            uuid.UUID(admin["id"]),
            body.server_name,
            exclude_id=target_id,
        ):
            raise HTTPException(
                status_code=409,
                detail=f"An MCP server named {body.server_name!r} already exists.",
            )
        mcp["server_name"] = body.server_name
        key.name = f"mcp:{body.server_name}"
        fields.append("server_name")

    if body.collection is not None:
        collection = await _validate_collection(session, body.collection)
        if collection:
            permissions["collection"] = collection
        else:
            permissions.pop("collection", None)
        fields.append("collection")

    permissions["mcp"] = mcp
    key.permissions = permissions

    await session.commit()
    await session.refresh(key)
    await invalidate_api_key_principal(previous_hash)
    audit.record(
        request,
        user=admin,
        action="mcp_server.update",
        resource_type="mcp_server",
        resource_id=str(key.id),
        metadata={"server_name": mcp.get("server_name"), "fields": fields},
    )
    return _to_response(key)


@router.post("/{server_id}/rotate", response_model=CreateMcpServerResponse)
async def rotate_mcp_server_key(
    server_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> CreateMcpServerResponse:

    try:
        target_id = uuid.UUID(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="MCP server not found") from e

    key = await session.get(ApiKey, target_id)
    if not _is_mcp(key) or key.user_id != uuid.UUID(admin["id"]):
        raise HTTPException(status_code=404, detail="MCP server not found")

    previous_hash = key.key_hash
    plaintext, prefix, key_hash = generate_api_key()
    key.key_hash = key_hash
    key.prefix = prefix
    key.active = True
    await session.commit()
    await session.refresh(key)
    await invalidate_api_key_principal(previous_hash)

    logger.info("mcp server rotated", id=str(key.id), actor=admin["email"])
    audit.record(
        request,
        user=admin,
        action="mcp_server.rotate",
        resource_type="mcp_server",
        resource_id=str(key.id),
        metadata={},
    )

    base = _to_response(key)
    return CreateMcpServerResponse(**base.model_dump(), api_key=plaintext)


@router.delete("/{server_id}", response_model=StatusResponse)
async def delete_mcp_server(
    server_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    try:
        target_id = uuid.UUID(server_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="MCP server not found") from e

    key = await session.get(ApiKey, target_id)
    if not _is_mcp(key) or key.user_id != uuid.UUID(admin["id"]):
        raise HTTPException(status_code=404, detail="MCP server not found")

    metadata = key.permissions.get("mcp", {}) if isinstance(key.permissions, dict) else {}
    deleted_hash = key.key_hash
    await session.delete(key)
    await session.commit()
    await invalidate_api_key_principal(deleted_hash)

    logger.info("mcp server deleted", id=server_id, actor=admin["email"])
    audit.record(
        request,
        user=admin,
        action="mcp_server.delete",
        resource_type="mcp_server",
        resource_id=server_id,
        metadata={
            "title": metadata.get("title"),
            "server_name": metadata.get("server_name"),
        },
    )
    return StatusResponse(status="ok", message="MCP server deleted")
