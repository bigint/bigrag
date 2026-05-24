from __future__ import annotations

import re

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "client_secret",
        "code",
        "csrf",
        "csrf_token",
        "embedding_api_key",
        "id_token",
        "rerank_api_key",
        "reranking_api_key",
        "oauth_token",
        "password",
        "password_hash",
        "proxy-authorization",
        "session_token",
        "state",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x_api_key",
        "apikey",
        "api_secret_key",
        "secret_key",
        "credential",
        "credentials",
        "signature",
        "signing_secret",
        "webhook_secret",
        "secret",
        "master_key",
        "master_key_previous",
    }
)
_SENSITIVE_COMPACT_KEYS = frozenset(
    key.replace("_", "").replace("-", "") for key in _SENSITIVE_KEYS
)
_SENSITIVE_KEY_MARKERS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "password",
        "secret",
        "credential",
        "signature",
    }
)
_MAX_LOG_VALUE_LENGTH = 2048
_CONTROL_CHAR_REPLACEMENTS = {
    "\n": r"\n",
    "\r": r"\r",
    "\t": r"\t",
    "\x1b": r"\x1b",
}


def is_sensitive_log_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    return (
        lowered in _SENSITIVE_KEYS
        or normalized in _SENSITIVE_KEYS
        or compact in _SENSITIVE_COMPACT_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or compact.endswith("token")
        or compact.endswith("secret")
        or any(marker in normalized or marker in compact for marker in _SENSITIVE_KEY_MARKERS)
    )


def truncate_log_value(value: str) -> str:
    if len(value) <= _MAX_LOG_VALUE_LENGTH:
        return value
    return f"{value[:_MAX_LOG_VALUE_LENGTH]}..."


def log_field_value(value: object) -> str:
    return truncate_log_value(escape_control_characters(str(value)))


def redact_secrets(_logger, _method_name, event_dict):
    return redact_log_value(event_dict)


def escape_control_characters(value: str) -> str:
    return "".join(
        _CONTROL_CHAR_REPLACEMENTS.get(char)
        or (f"\\x{ord(char):02x}" if ord(char) < 32 or 127 <= ord(char) <= 159 else char)
        for char in value
    )


def redact_log_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if is_sensitive_log_key(key) else redact_log_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_log_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_log_value(item) for item in value)
    if isinstance(value, str):
        return truncate_log_value(value)
    return value
