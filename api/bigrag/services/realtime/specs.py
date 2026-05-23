from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

SnapshotLoader = Callable[[], Awaitable[Any]]
SnapshotInterval = Callable[[Any | None], float]
SnapshotDone = Callable[[Any], bool]


class TopicError(Exception):
    pass


@dataclass
class SnapshotTopic:
    topic: str
    load: SnapshotLoader
    interval_for: SnapshotInterval
    event_key: str | None = None
    done: SnapshotDone | None = None


@dataclass
class EventTopic:
    topic: str
    event_key: str
    connected_payload: dict[str, Any] | None = None


RealtimeTopic = SnapshotTopic | EventTopic


def fixed(seconds: float) -> SnapshotInterval:
    return lambda _payload: seconds
