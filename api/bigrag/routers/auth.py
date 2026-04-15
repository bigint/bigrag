"""Authentication endpoints: setup, login, logout, me, change password."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.config import settings
from bigrag.db.models import Session as DbSession
from bigrag.db.models import User
from bigrag.db.session import get_session
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
    WhoamiResponse,
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


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
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


async def _issue_session(session: AsyncSession, user_id: uuid.UUID) -> str:
    token = generate_session_token()
    session.add(
        DbSession(
            id=uuid.uuid4(),
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=session_expiry(),
        )
    )
    return token


@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status(
    session: AsyncSession = Depends(get_session),
) -> SetupStatusResponse:
    count = await session.scalar(sa.select(sa.func.count()).select_from(User))
    return SetupStatusResponse(needs_setup=count == 0)


@router.post("/setup", response_model=SessionResponse, status_code=201)
async def setup(
    body: SetupRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    existing = await session.scalar(sa.select(sa.func.count()).select_from(User))
    if existing > 0:
        raise HTTPException(status_code=403, detail="Setup has already been completed")

    user = User(
        id=uuid.uuid4(),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        role="admin",
        last_login_at=sa.func.now(),
    )
    session.add(user)
    await session.flush()
    token = await _issue_session(session, user.id)
    await session.commit()
    await session.refresh(user)

    _set_session_cookie(response, token)
    logger.info(f"First admin created: {body.email}")
    return SessionResponse(user=_user_response(user))


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    user = await session.scalar(sa.select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    user.last_login_at = sa.func.now()
    token = await _issue_session(session, user.id)
    await session.commit()
    await session.refresh(user)
    _set_session_cookie(response, token)
    return SessionResponse(user=_user_response(user))


@router.post("/logout", response_model=StatusResponse)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    cookie = request.cookies.get(settings.session_cookie_name)
    if cookie:
        await session.execute(
            sa.delete(DbSession).where(DbSession.token_hash == hash_session_token(cookie))
        )
        await session.commit()
    _clear_session_cookie(response)
    return StatusResponse(status="ok", message="Logged out")


@router.post("/logout-all", response_model=StatusResponse)
async def logout_all(
    response: Response,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    """Revoke every session for the current user.

    Used from the Studio's "Sign out everywhere" action when a user suspects
    a device or session is compromised. The current browser cookie is also
    cleared so the caller lands on the login page.
    """
    await session.execute(sa.delete(DbSession).where(DbSession.user_id == uuid.UUID(user["id"])))
    await session.commit()
    _clear_session_cookie(response)
    return StatusResponse(status="ok", message="Signed out of all devices")


@router.get("/me", response_model=SessionResponse)
async def me(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    target = await session.get(User, uuid.UUID(user["id"]))
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    return SessionResponse(user=_user_response(target))


@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(user: dict = Depends(get_current_user)) -> WhoamiResponse:
    """Return the current principal's identity and scope.

    Used by the MCP server to self-configure: an API key with a
    `collection` pin auto-scopes the exposed tools.
    """
    return WhoamiResponse(
        auth_method=user.get("auth_method", "session"),
        user_id=user["id"],
        user_email=user["email"],
        api_key_id=user.get("api_key_id"),
        api_key_name=user.get("api_key_name"),
        scopes=user.get("scopes"),
        collection=user.get("collection"),
    )


@router.post("/password", response_model=StatusResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    target = await session.get(User, uuid.UUID(user["id"]))
    if target is None or not verify_password(body.current_password, target.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    target.password_hash = hash_password(body.new_password)
    await session.execute(sa.delete(DbSession).where(DbSession.user_id == target.id))
    await session.commit()
    return StatusResponse(status="ok", message="Password updated — please sign in again")
