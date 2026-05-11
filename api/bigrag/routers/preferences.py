from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import UserPreference
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.services import crypto
from bigrag.services.credential_check import CredentialCheckError, verify_provider_credentials

logger = get_logger("bigrag.routers.preferences")

router = APIRouter(prefix="/v1/auth/preferences", tags=["auth"])

_SENSITIVE_PATHS: frozenset[tuple[str, str]] = frozenset({("chat", "openai_key")})


def _deep_merge(left: dict, right: dict) -> dict:
    out = {**left}
    for key, value in right.items():
        existing = out.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            out[key] = _deep_merge(existing, value)
        else:
            out[key] = value
    return out


def _normalize_sensitive(data: dict) -> dict:
    out = {**data}
    for parent, key in _SENSITIVE_PATHS:
        sub = out.get(parent)
        if not isinstance(sub, dict) or key not in sub:
            continue
        value = sub[key]
        if isinstance(value, str):
            out[parent] = {**sub, key: value.strip()}
    return out


async def _validate_sensitive(data: dict) -> None:
    chat = data.get("chat")
    if not isinstance(chat, dict) or "openai_key" not in chat:
        return

    value = chat.get("openai_key")
    if value is None or value == "":
        return
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail="OpenAI API key must be a string.")

    try:
        await verify_provider_credentials("openai", value, None)
    except CredentialCheckError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "OpenAI rejected this API key. Create a fresh key from the OpenAI API "
                "keys page and try again."
            ),
        ) from exc


def _encrypt_sensitive(data: dict) -> dict:
    if not isinstance(data, dict) or not crypto.is_configured():
        return data
    out = {**data}
    for parent, key in _SENSITIVE_PATHS:
        sub = out.get(parent)
        if not isinstance(sub, dict) or key not in sub:
            continue
        value = sub[key]
        if not isinstance(value, str) or not value:
            continue
        if value.startswith(crypto._FERNET_PREFIX):
            continue
        out[parent] = {**sub, key: crypto.encrypt(value)}
    return out


def _remove_cleared_sensitive(merged: dict, incoming: dict) -> dict:
    out = {**merged}
    for parent, key in _SENSITIVE_PATHS:
        sub_in = incoming.get(parent)
        if not isinstance(sub_in, dict) or sub_in.get(key) not in ("", None):
            continue
        sub_out = out.get(parent)
        if not isinstance(sub_out, dict):
            continue
        cleaned = {**sub_out}
        cleaned.pop(key, None)
        out[parent] = cleaned
    return out


def _decrypt_sensitive(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    out = {**data}
    for parent, key in _SENSITIVE_PATHS:
        sub = out.get(parent)
        if not isinstance(sub, dict) or key not in sub:
            continue
        value = sub[key]
        if not isinstance(value, str) or not value:
            continue
        if not value.startswith(crypto._FERNET_PREFIX):
            continue
        if not crypto.is_configured():
            continue
        try:
            decrypted = crypto.decrypt(value)
        except ValueError:
            logger.warning("preferences: failed to decrypt sensitive value at %s.%s", parent, key)
            continue
        out[parent] = {**sub, key: decrypted}
    return out


def decrypt_preferences(data: dict) -> dict:
    return _decrypt_sensitive(dict(data)) if isinstance(data, dict) else {}


def _public_preferences(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    out = {**data}
    for parent, key in _SENSITIVE_PATHS:
        sub = out.get(parent)
        if not isinstance(sub, dict):
            continue
        cleaned = {**sub}
        if key in cleaned:
            value = cleaned.pop(key)
            cleaned[f"has_{key}"] = bool(value)
        out[parent] = cleaned
    return out


@router.get("", response_model=dict[str, dict])
async def get_preferences(
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.scalar(
        sa.select(UserPreference).where(UserPreference.user_id == uuid.UUID(user["id"]))
    )
    return {"data": _public_preferences(dict(row.data)) if row else {}}


@router.put("", response_model=dict[str, dict])
async def update_preferences(
    body: dict,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:

    incoming = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(incoming, dict):
        incoming = {}

    user_id = uuid.UUID(user["id"])
    existing_row = await session.scalar(
        sa.select(UserPreference).where(UserPreference.user_id == user_id)
    )
    existing = dict(existing_row.data) if existing_row else {}
    incoming = _normalize_sensitive(incoming)
    await _validate_sensitive(incoming)
    incoming = _encrypt_sensitive(incoming)
    merged = _remove_cleared_sensitive(_deep_merge(existing, incoming), incoming)

    stmt = pg_insert(UserPreference).values(user_id=user_id, data=merged)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserPreference.user_id],
        set_={
            "data": stmt.excluded.data,
            "updated_at": sa.func.now(),
        },
    ).returning(UserPreference.data)
    result = await session.execute(stmt)
    await session.commit()
    return {"data": _public_preferences(dict(result.scalar_one()))}
