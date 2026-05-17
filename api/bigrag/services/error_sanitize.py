from __future__ import annotations

import re

from bigrag.exceptions import NotFoundError, ServerError, UpstreamError, ValidationError

_SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}"
    r"|sk-[A-Za-z0-9_-]{8,}"
    r"|AIza[0-9A-Za-z_-]{20,}"
)
_CONTEXTUAL_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer)([\"'\s:=]+)([A-Za-z0-9_\-]{40,})"
)

_PUBLIC_ERRORS = (ValidationError, NotFoundError, ServerError, UpstreamError)


def sanitize_error_message(exc: Exception, fallback: str = "request failed") -> str:
    if isinstance(exc, _PUBLIC_ERRORS):
        message = str(exc)
    else:
        message = getattr(exc, "message", None) or str(exc) or fallback
    message = _SECRET_RE.sub("[REDACTED]", message)
    message = _CONTEXTUAL_SECRET_RE.sub(r"\1\2[REDACTED]", message)
    return message[:500]


def sanitize_message_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = _SECRET_RE.sub("[REDACTED]", text)
    cleaned = _CONTEXTUAL_SECRET_RE.sub(r"\1\2[REDACTED]", cleaned)
    return cleaned[:500]
