from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import orjson


@dataclass
class IngestionEvent:
    document_id: str
    step: str
    status: str
    message: str
    progress: float = 0.0
    detail: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        data = {
            "document_id": self.document_id,
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            **self.detail,
        }
        return f"data: {orjson.dumps(data).decode()}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[IngestionEvent | None]]] = {}

    def subscribe(self, document_id: str) -> asyncio.Queue[IngestionEvent | None]:
        q: asyncio.Queue[IngestionEvent | None] = asyncio.Queue()
        self._subs.setdefault(document_id, []).append(q)
        return q

    def unsubscribe(self, document_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(document_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subs.pop(document_id, None)

    def publish(self, event: IngestionEvent) -> None:
        for q in self._subs.get(event.document_id, []):
            q.put_nowait(event)
        for q in self._subs.get("*", []):
            q.put_nowait(event)

    def complete(self, document_id: str) -> None:
        for q in self._subs.get(document_id, []):
            q.put_nowait(None)

    async def stream(self, document_id: str) -> AsyncIterator[IngestionEvent]:
        q = self.subscribe(document_id)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield event
        finally:
            self.unsubscribe(document_id, q)


event_bus = EventBus()
