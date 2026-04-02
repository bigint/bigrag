from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from bigrag.middleware.auth import get_current_user

logger = logging.getLogger("bigrag.routers.auth")
from bigrag.middleware.rate_limit import auth_rate_limit
from bigrag.models.auth import (
    AuthResponse,
    LoginRequest,
    PasswordChangeRequest,
    SetupRequest,
    UserResponse,
)
from bigrag.services import auth as auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/setup-status")
async def setup_status():
    needs = await auth_service.needs_setup()
    logger.info(f"setup-status: needs_setup={needs}")
    return {"needs_setup": needs}


@router.post("/setup", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
async def setup(body: SetupRequest):
    logger.info(f"setup: email={body.email}")
    if not await auth_service.needs_setup():
        raise HTTPException(status_code=409, detail="Setup already completed")

    user = await auth_service.create_user(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        role="admin",
    )
    logger.info(f"setup: admin user created email={body.email}")
    token = await auth_service.create_session(user["id"])
    return AuthResponse(
        token=token,
        user=UserResponse(**{k: str(v) if isinstance(v, UUID) else v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginRequest):
    logger.info(f"login: email={body.email}")
    user = await auth_service.authenticate(body.email, body.password)
    if not user:
        logger.warning(f"login: failed email={body.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logger.info(f"login: success email={body.email}")
    token = await auth_service.create_session(user["id"])
    return AuthResponse(
        token=token,
        user=UserResponse(**{k: str(v) if isinstance(v, UUID) else v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/logout")
async def logout_route(request: Request, user: dict = Depends(get_current_user)):
    logger.info(f"logout: user={user.get('email')}")
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        token_hash = auth_service.hash_token(token)
        await auth_service.invalidate_session(token)
        from bigrag.middleware.auth import invalidate_auth_cache
        invalidate_auth_cache(token_hash)
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user": {
            "id": str(user["id"]) if user.get("id") else None,
            "email": user.get("email", ""),
            "display_name": user.get("display_name", ""),
            "role": user.get("role", "admin"),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        }
    }


@router.put("/password")
async def change_password(body: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    logger.info(f"password change: user={user.get('email')}")
    if not user.get("id"):
        raise HTTPException(status_code=400, detail="Cannot change password for this account type")

    success = await auth_service.change_password(
        user["id"], body.current_password, body.new_password
    )
    if not success:
        logger.warning(f"password change: wrong current password user={user.get('email')}")
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    logger.info(f"password change: success user={user.get('email')}")
    return {"status": "ok"}
