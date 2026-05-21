from __future__ import annotations

from fastapi import HTTPException

from bigrag.logging import get_logger
from bigrag.services import crypto
from bigrag.services.credential_check import CredentialCheckError, verify_provider_credentials

logger = get_logger("bigrag.services.preferences")

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

    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["chat_provider", "chat_base_url"])
    try:
        await verify_provider_credentials(
            runtime["chat_provider"],
            value,
            runtime["chat_base_url"],
            url_purpose="chat",
        )
    except CredentialCheckError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Chat provider rejected this API key. Check the configured chat "
                "provider and base URL, then try again."
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
            logger.warning(
                "preferences: failed to decrypt sensitive value at %s.%s; dropping",
                parent,
                key,
            )
            cleaned = {**sub}
            cleaned.pop(key, None)
            out[parent] = cleaned
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
