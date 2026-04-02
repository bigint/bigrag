from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.middleware.auth import require_admin

logger = logging.getLogger("bigrag.routers.admin")
from bigrag.models.auth import CreateApiKeyRequest
from bigrag.services import auth as auth_service

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.post("/api-keys")
async def create_api_key(body: CreateApiKeyRequest, admin: dict = Depends(require_admin)):
    logger.info(f"create api key: name={body.name} by={admin.get('email')}")
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
    logger.info(f"create api key: done name={body.name} prefix={record['prefix']}")
    return result


@router.get("/api-keys")
async def list_api_keys(limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0), _: dict = Depends(require_admin)):
    keys = await auth_service.list_api_keys(limit=limit, offset=offset)
    return {
        "keys": [
            {k: str(v) if isinstance(v, UUID) else v for k, v in key.items()}
            for key in keys
        ]
    }


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, _: dict = Depends(require_admin)):
    logger.info(f"delete api key: id={key_id}")
    if not await auth_service.delete_api_key(UUID(key_id)):
        raise HTTPException(status_code=404, detail="API key not found")
    logger.info(f"delete api key: done id={key_id}")
    return {"status": "ok", "message": "API key deleted"}
