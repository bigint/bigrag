from __future__ import annotations

import os
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as _config
from bigrag.db.models import User, UserSession
from bigrag.db.session import get_session
from bigrag.ids import uuid7
from bigrag.logging import get_logger
from bigrag.middleware.auth import (
    get_current_user,
    invalidate_auth_principals,
    invalidate_session_principal,
    require_session,
    session_expiry,
)
from bigrag.models import StatusResponse
from bigrag.models.auth import (
    ChangePasswordRequest,
    LoginRequest,
    SessionResponse,
    SetupRequest,
    SetupStatusResponse,
    UserResponse,
    WhoamiResponse,
)
from bigrag.services import audit
from bigrag.services.auth import (
    DUMMY_PASSWORD_HASH,
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)
from bigrag.services.client_ip import client_ip
from bigrag.services.redis_cache import get_redis
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.routers.auth")

router = APIRouter(prefix="/v1/auth", tags=["auth"])

LOGIN_RATE_LIMIT = int(os.environ.get("BIGRAG_LOGIN_RATE_LIMIT", "10"))
LOGIN_RATE_WINDOW_SECONDS = int(os.environ.get("BIGRAG_LOGIN_RATE_WINDOW_SECONDS", "60"))
SETUP_LOCK_KEY = 734119001


async def _enforce_login_rate_limit(request: Request, email: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    ip = client_ip(request) or "unknown"
    for scope, key in (("ip", ip), ("email", email)):
        bucket = f"bigrag:rate:login:{scope}:{key}"
        try:
            pipeline = redis.pipeline()
            pipeline.incr(bucket)
            pipeline.expire(bucket, LOGIN_RATE_WINDOW_SECONDS)
            results = await pipeline.execute()
            current = results[0]
        except Exception as exc:
            logger.warning(
                "login rate limit unavailable; failing open",
                scope=scope,
                error=str(exc),
            )
            return
        if current > LOGIN_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again in a minute.",
            )


async def _session_cookie_options() -> dict:
    return await get_values(
        [
            "session_cookie_secure",
            "session_cookie_samesite",
            "session_cookie_domain",
        ]
    )


async def _lock_setup(session: AsyncSession) -> None:
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=SETUP_LOCK_KEY)
    )


async def _set_session_cookie(response: Response, token: str) -> None:
    cookie = await _session_cookie_options()
    response.set_cookie(
        key=_config.settings.session_cookie_name,
        value=token,
        max_age=_config.settings.session_expiry_hours * 3600,
        httponly=True,
        secure=bool(cookie["session_cookie_secure"]),
        samesite=cookie["session_cookie_samesite"] or "lax",
        domain=cookie["session_cookie_domain"],
        path="/",
    )


async def _clear_session_cookie(response: Response) -> None:
    cookie = await _session_cookie_options()
    response.delete_cookie(
        key=_config.settings.session_cookie_name,
        httponly=True,
        secure=bool(cookie["session_cookie_secure"]),
        samesite=cookie["session_cookie_samesite"] or "lax",
        domain=cookie["session_cookie_domain"],
        path="/",
    )


async def _issue_session(session: AsyncSession, user_id: uuid.UUID) -> str:
    token = generate_session_token()
    session.add(
        UserSession(
            id=uuid7(),
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
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    await _lock_setup(session)
    existing = await session.scalar(sa.select(sa.func.count()).select_from(User))
    if existing > 0:
        raise HTTPException(status_code=409, detail="Setup has already been completed")

    user = User(
        id=uuid7(),
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

    await _set_session_cookie(response, token)
    logger.info("first admin created", email=body.email)
    audit.record(
        request,
        user={"id": str(user.id), "email": user.email},
        action="auth.setup",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"email": user.email, "role": "admin"},
    )
    return SessionResponse(user=UserResponse.from_user(user))


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    email = body.email.lower()
    await _enforce_login_rate_limit(request, email)
    user = await session.scalar(sa.select(User).where(User.email == email))
    if user is None:
        verify_password(body.password, DUMMY_PASSWORD_HASH)
        password_ok = False
    else:
        password_ok = verify_password(body.password, user.password_hash)
    if user is None or not password_ok:
        audit.record(
            request,
            user={"id": None, "email": email},
            action="auth.login_failed",
            resource_type="user",
            resource_id=None,
            metadata={"email": email},
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    user.last_login_at = sa.func.now()
    token = await _issue_session(session, user.id)
    await session.commit()
    await session.refresh(user)
    await _set_session_cookie(response, token)
    audit.record(
        request,
        user={"id": str(user.id), "email": user.email},
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        metadata={},
    )
    return SessionResponse(user=UserResponse.from_user(user))


@router.post("/logout", response_model=StatusResponse)
async def logout(
    request: Request,
    response: Response,
    auth_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    cookie = request.cookies.get(_config.settings.session_cookie_name)
    actor_user: User | None = None
    if cookie:
        token_hash = hash_session_token(cookie)
        actor_user = await session.scalar(
            sa.select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash)
        )
        if actor_user is None or str(actor_user.id) != auth_user["id"]:
            await _clear_session_cookie(response)
            raise HTTPException(status_code=403, detail="Session mismatch")
        await session.execute(sa.delete(UserSession).where(UserSession.token_hash == token_hash))
        await session.commit()
        await invalidate_session_principal(token_hash)
    await _clear_session_cookie(response)
    if actor_user is not None:
        audit.record(
            request,
            user={"id": str(actor_user.id), "email": actor_user.email},
            action="auth.logout",
            resource_type="user",
            resource_id=str(actor_user.id),
            metadata={},
        )
    return StatusResponse(status="ok", message="Logged out")


@router.post("/logout-all", response_model=StatusResponse)
async def logout_all(
    request: Request,
    response: Response,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    if user.get("auth_method") != "session":
        raise HTTPException(status_code=403, detail="Session authentication required")
    await session.execute(
        sa.delete(UserSession).where(UserSession.user_id == uuid.UUID(user["id"]))
    )
    await session.commit()
    await invalidate_auth_principals()
    await _clear_session_cookie(response)
    audit.record(
        request,
        user=user,
        action="auth.logout_all",
        resource_type="user",
        resource_id=user["id"],
        metadata={},
    )
    return StatusResponse(status="ok", message="Signed out of all devices")


@router.get("/me", response_model=SessionResponse)
async def me(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    target = await session.get(User, uuid.UUID(user["id"]))
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    return SessionResponse(user=UserResponse.from_user(target))


@router.get("/whoami", response_model=WhoamiResponse)
async def whoami(user: dict = Depends(get_current_user)) -> WhoamiResponse:

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
    request: Request,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:
    target = await session.get(User, uuid.UUID(user["id"]))
    if target is None or not verify_password(body.current_password, target.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    target.password_hash = hash_password(body.new_password)
    await session.execute(sa.delete(UserSession).where(UserSession.user_id == target.id))
    await session.commit()
    await invalidate_auth_principals()
    audit.record(
        request,
        user=user,
        action="user.password_change",
        resource_type="user",
        resource_id=str(target.id),
        metadata={},
    )
    return StatusResponse(status="ok", message="Password updated — please sign in again")
