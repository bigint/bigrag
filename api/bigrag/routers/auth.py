"""Authentication endpoints: setup, login, logout, me, change password."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from bigrag.config import settings
from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.middleware.auth import (
    get_current_user,
    require_session,
    session_expiry,
)
from bigrag.models.auth import (
    ChangePasswordRequest,
    LoginRequest,
    SessionResponse,
    SetupRequest,
    SetupStatusResponse,
    UserResponse,
)
from bigrag.models.common import StatusResponse
from bigrag.services.auth import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)

logger = get_logger("bigrag.routers.auth")

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _user_response(row: dict) -> UserResponse:
    return UserResponse(
        id=str(row["id"]),
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"],
        last_login_at=row.get("last_login_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_expiry_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        domain=settings.session_cookie_domain,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.session_cookie_domain,
        path="/",
    )


async def _issue_session(user_id: uuid.UUID) -> str:
    token = generate_session_token()
    token_hash = hash_session_token(token)
    await db.execute(
        """
        INSERT INTO sessions (id, user_id, token_hash, expires_at)
        VALUES ($1, $2, $3, $4)
        """,
        uuid.uuid4(),
        user_id,
        token_hash,
        session_expiry(),
    )
    return token


@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status() -> SetupStatusResponse:
    row = await db.fetchrow("SELECT COUNT(*) AS cnt FROM users")
    return SetupStatusResponse(needs_setup=row["cnt"] == 0)


@router.post("/setup", response_model=SessionResponse, status_code=201)
async def setup(body: SetupRequest, response: Response) -> SessionResponse:
    existing = await db.fetchrow("SELECT COUNT(*) AS cnt FROM users")
    if existing["cnt"] > 0:
        raise HTTPException(status_code=403, detail="Setup has already been completed")

    user_id = uuid.uuid4()
    row = await db.fetchrow(
        """
        INSERT INTO users (id, email, password_hash, display_name, role, last_login_at)
        VALUES ($1, $2, $3, $4, 'admin', now())
        RETURNING *
        """,
        user_id,
        body.email.lower(),
        hash_password(body.password),
        body.display_name,
    )
    token = await _issue_session(user_id)
    _set_session_cookie(response, token)
    logger.info(f"First admin created: {body.email}")
    return SessionResponse(user=_user_response(dict(row)))


@router.post("/login", response_model=SessionResponse)
async def login(body: LoginRequest, response: Response) -> SessionResponse:
    row = await db.fetchrow(
        "SELECT * FROM users WHERE email = $1",
        body.email.lower(),
    )
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if needs_rehash(row["password_hash"]):
        await db.execute(
            "UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2",
            hash_password(body.password),
            row["id"],
        )

    await db.execute(
        "UPDATE users SET last_login_at = now() WHERE id = $1",
        row["id"],
    )
    token = await _issue_session(row["id"])
    _set_session_cookie(response, token)

    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", row["id"])
    return SessionResponse(user=_user_response(dict(row)))


@router.post("/logout", response_model=StatusResponse)
async def logout(request: Request, response: Response) -> StatusResponse:
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie:
        await db.execute(
            "DELETE FROM sessions WHERE token_hash = $1",
            hash_session_token(cookie),
        )
    _clear_session_cookie(response)
    return StatusResponse(status="ok", message="Logged out")


@router.post("/logout-all", response_model=StatusResponse)
async def logout_all(
    response: Response,
    user: dict = Depends(get_current_user),
) -> StatusResponse:
    """Revoke every session for the current user.

    Used from the Studio's "Sign out everywhere" action when a user
    suspects a device or session is compromised. The current browser
    cookie is also cleared so the caller lands on the login page.
    """
    await db.execute(
        "DELETE FROM sessions WHERE user_id = $1",
        uuid.UUID(user["id"]),
    )
    _clear_session_cookie(response)
    return StatusResponse(status="ok", message="Signed out of all devices")


@router.get("/me", response_model=SessionResponse)
async def me(user: dict = Depends(get_current_user)) -> SessionResponse:
    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", uuid.UUID(user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return SessionResponse(user=_user_response(dict(row)))


@router.post("/password", response_model=StatusResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_session),
) -> StatusResponse:
    row = await db.fetchrow(
        "SELECT password_hash FROM users WHERE id = $1",
        uuid.UUID(user["id"]),
    )
    if not row or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    await db.execute(
        "UPDATE users SET password_hash = $1, updated_at = now() WHERE id = $2",
        hash_password(body.new_password),
        uuid.UUID(user["id"]),
    )
    await db.execute("DELETE FROM sessions WHERE user_id = $1", uuid.UUID(user["id"]))
    return StatusResponse(status="ok", message="Password updated — please sign in again")
