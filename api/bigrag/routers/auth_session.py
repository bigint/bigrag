from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import config as _config
from bigrag.db.models import UserSession
from bigrag.ids import uuid7
from bigrag.middleware.auth import session_expiry
from bigrag.services.auth import generate_session_token, hash_session_token
from bigrag.services.runtime_settings import get_values

SETUP_LOCK_KEY = 734119001


async def session_cookie_options() -> dict:
    return await get_values(
        [
            "session_cookie_secure",
            "session_cookie_samesite",
            "session_cookie_domain",
        ]
    )


async def lock_setup(session: AsyncSession) -> None:
    await session.execute(
        sa.text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=SETUP_LOCK_KEY)
    )


async def set_session_cookie(response: Response, token: str) -> None:
    cookie = await session_cookie_options()
    secure, samesite = resolve_cookie_security(cookie)
    response.set_cookie(
        key=_config.settings.session_cookie_name,
        value=token,
        max_age=_config.settings.session_expiry_hours * 3600,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=cookie["session_cookie_domain"],
        path="/",
    )


async def clear_session_cookie(response: Response) -> None:
    cookie = await session_cookie_options()
    secure, samesite = resolve_cookie_security(cookie)
    response.delete_cookie(
        key=_config.settings.session_cookie_name,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=cookie["session_cookie_domain"],
        path="/",
    )


async def issue_session(session: AsyncSession, user_id: uuid.UUID) -> str:
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


def resolve_cookie_security(cookie: dict) -> tuple[bool, str]:
    samesite = cookie["session_cookie_samesite"] or "lax"
    secure = bool(cookie["session_cookie_secure"])
    if samesite.lower() == "none":
        secure = True
    return secure, samesite
