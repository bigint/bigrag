"""SSE progress event types."""

from __future__ import annotations

from bigrag.types._compat import Any, NotRequired, TypedDict


class ProgressEvent(TypedDict):
    step: str
    message: str
    progress: float
    status: NotRequired[str]
    detail: NotRequired[dict[str, Any]]
