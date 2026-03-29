from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from bigrag.middleware.auth import require_admin
from bigrag.models.auth import (
    CreateApiKeyRequest,
    CreateInviteRequest,
    UpdateRoleRequest,
)
from bigrag.services import auth as auth_service

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# --- Users ---


@router.get("/users")
async def list_users(limit: int = 100, offset: int = 0, _: dict = Depends(require_admin)):
    users = await auth_service.list_users(limit=limit, offset=offset)
    return {
        "users": [
            {k: str(v) if isinstance(v, UUID) else v for k, v in u.items()}
            for u in users
        ]
    }


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    uid = UUID(user_id)
    if admin.get("id") and uid == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if not await auth_service.delete_user(uid):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok", "message": "User deleted"}


@router.patch("/users/{user_id}")
async def update_user_role(user_id: str, body: UpdateRoleRequest, _: dict = Depends(require_admin)):
    if not await auth_service.update_user_role(UUID(user_id), body.role):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}


# --- Invites ---


@router.post("/invites")
async def create_invite(body: CreateInviteRequest, admin: dict = Depends(require_admin)):
    invite = await auth_service.create_invite(
        created_by=admin["id"],
        role=body.role,
        expires_in_hours=body.expires_in_hours,
    )
    return {k: str(v) if isinstance(v, UUID) else v for k, v in invite.items()}


@router.get("/invites")
async def list_invites(limit: int = 100, offset: int = 0, _: dict = Depends(require_admin)):
    invites = await auth_service.list_invites(limit=limit, offset=offset)
    return {
        "invites": [
            {k: str(v) if isinstance(v, UUID) else v for k, v in inv.items()}
            for inv in invites
        ]
    }


@router.delete("/invites/{invite_id}")
async def delete_invite(invite_id: str, _: dict = Depends(require_admin)):
    if not await auth_service.delete_invite(UUID(invite_id)):
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"status": "ok", "message": "Invite deleted"}


# --- API Keys ---


@router.post("/api-keys")
async def create_api_key(body: CreateApiKeyRequest, admin: dict = Depends(require_admin)):
    permissions = {
        "collections": body.collections,
        "operations": body.operations,
        "admin": body.admin,
    }
    key, record = await auth_service.create_api_key_record(
        user_id=admin.get("id"),
        name=body.name,
        permissions=permissions,
        expires_at=body.expires_at,
    )
    result = {k: str(v) if isinstance(v, UUID) else v for k, v in record.items()}
    result["key"] = key
    return result


@router.get("/api-keys")
async def list_api_keys(limit: int = 100, offset: int = 0, _: dict = Depends(require_admin)):
    keys = await auth_service.list_api_keys(limit=limit, offset=offset)
    return {
        "keys": [
            {k: str(v) if isinstance(v, UUID) else v for k, v in key.items()}
            for key in keys
        ]
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, _: dict = Depends(require_admin)):
    if not await auth_service.delete_api_key(UUID(key_id)):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "ok", "message": "API key deleted"}
