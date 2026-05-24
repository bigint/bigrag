from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class RealtimeSnapshot(TypedDict):
    type: Literal["snapshot"]
    id: str
    topic: str
    payload: Any
    generated_at: str


class RealtimeEvent(TypedDict):
    type: Literal["event"]
    id: str
    topic: str
    payload: Any
    generated_at: str


class RealtimeError(TypedDict):
    type: Literal["error"]
    message: str
    id: NotRequired[str]
    topic: NotRequired[str]
    generated_at: str


class RealtimeComplete(TypedDict):
    type: Literal["complete"]
    id: str
    topic: str
    generated_at: str


class RealtimeControlMessage(TypedDict):
    type: Literal["subscribed", "heartbeat", "pong"]
    id: NotRequired[str]
    topic: NotRequired[str]
    generated_at: NotRequired[str]


RealtimeMessage = (
    RealtimeSnapshot | RealtimeEvent | RealtimeError | RealtimeComplete | RealtimeControlMessage
)


class ProgressEvent(TypedDict):
    step: str
    message: str
    progress: float
    document_id: NotRequired[str]
    status: NotRequired[str]
    detail: NotRequired[dict[str, Any]]
