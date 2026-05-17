
from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class ProgressEvent(TypedDict):
    step: str
    message: str
    progress: float
    status: NotRequired[str]
    detail: NotRequired[dict[str, Any]]
