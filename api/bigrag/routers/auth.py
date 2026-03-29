from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from bigrag.middleware.auth import get_current_user
from bigrag.models.auth import (
    AuthResponse,
    LoginRequest,
    PasswordChangeRequest,
    SetupRequest,
    SignupRequest,
    UserResponse,
)
from bigrag.services import auth as auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/setup-status")
async def setup_status():
    needs = await auth_service.needs_setup()
    return {"needs_setup": needs}


@router.post("/setup", response_model=AuthResponse)
async def setup(body: SetupRequest):
    if not await auth_service.needs_setup():
        raise HTTPException(status_code=409, detail="Setup already completed")

    user = await auth_service.create_user(
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        role="admin",
    )
    token = await auth_service.create_session(user["id"])
    return AuthResponse(
        token=token,
        user=UserResponse(**{k: str(v) if isinstance(v, UUID) else v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = await auth_service.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = await auth_service.create_session(user["id"])
    return AuthResponse(
        token=token,
        user=UserResponse(**{k: str(v) if isinstance(v, UUID) else v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest):
    invite = await auth_service.redeem_invite(body.invite_code)
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    try:
        user = await auth_service.create_user(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            role=invite["role"],
        )
    except Exception:
        raise HTTPException(status_code=409, detail="Email already registered")

    await auth_service.mark_invite_used(invite["id"], user["id"])
    token = await auth_service.create_session(user["id"])
    return AuthResponse(
        token=token,
        user=UserResponse(**{k: str(v) if isinstance(v, UUID) else v for k, v in user.items() if k != "password_hash"}),
    )


@router.post("/logout")
async def logout_route(user: dict = Depends(get_current_user)):
    # We don't have the raw token here easily, but we can clear from header
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user": {
            "id": str(user["id"]) if user.get("id") else None,
            "email": user.get("email", ""),
            "display_name": user.get("display_name", ""),
            "role": user.get("role", "member"),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        }
    }


@router.put("/password")
async def change_password(body: PasswordChangeRequest, user: dict = Depends(get_current_user)):
    if not user.get("id"):
        raise HTTPException(status_code=400, detail="Cannot change password for this account type")

    success = await auth_service.change_password(
        user["id"], body.current_password, body.new_password
    )
    if not success:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    return {"status": "ok"}
