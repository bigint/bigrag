"""Redis-backed event bus for cross-process ingestion events."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field

import orjson
import redis.asyncio as aioredis

from bigrag.logging import get_logger

logger = get_logger("bigrag.event_bus")

CHANNEL_PREFIX = "bigrag:events:"


@dataclass
class IngestionEvent:
    document_id: str
    step: str
    status: str
    message: str
    progress: float = 0.0
    detail: dict = field(default_factory=dict)
    collection_name: str = ""

    def to_sse(self) -> str:
        data = {
            "document_id": self.document_id,
            "collection_name": self.collection_name,
            "step": self.step,
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            **self.detail,
        }
        return f"data: {orjson.dumps(data).decode()}\n\n"

    def serialize(self) -> bytes:
        return orjson.dumps(asdict(self))

    @classmethod
    def deserialize(cls, data: bytes) -> IngestionEvent:
        d = orjson.loads(data)
        return cls(
            document_id=d["document_id"],
            step=d["step"],
            status=d["status"],
            message=d["message"],
            progress=d.get("progress", 0.0),
            detail=d.get("detail", {}),
            collection_name=d.get("collection_name", ""),
        )


class EventBus:
    """Redis pub/sub event bus.

    Publishes events to Redis channels and dispatches incoming messages
    to local asyncio queues. Works across multiple server processes.
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener: asyncio.Task | None = None
        self._subs: dict[str, list[asyncio.Queue[IngestionEvent | None]]] = {}

    async def connect(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=False)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
        self._listener = asyncio.create_task(self._listen())
        logger.info("event bus connected to Redis")

    async def close(self) -> None:
        if self._listener:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("event bus: listener task failed during shutdown", error=str(e))
        if self._pubsub:
            await self._pubsub.punsubscribe()
            await self._pubsub.aclose()
        if self._redis:
            await self._redis.aclose()
        logger.info("event bus closed")

    async def _listen(self) -> None:
        """Read messages from Redis and dispatch to local queues."""
        async for message in self._pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                channel: str = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                key = channel.removeprefix(CHANNEL_PREFIX)
                event = IngestionEvent.deserialize(message["data"])
                self._dispatch(key, event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("event bus: bad message", error=str(e))

    def _dispatch(self, channel_key: str, event: IngestionEvent) -> None:
        """Route an event to matching local subscriber queues."""
        for q in self._subs.get(channel_key, []):
            q.put_nowait(event)
        for q in self._subs.get("*", []):
            q.put_nowait(event)

    def subscribe(self, key: str) -> asyncio.Queue[IngestionEvent | None]:
        q: asyncio.Queue[IngestionEvent | None] = asyncio.Queue()
        self._subs.setdefault(key, []).append(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(key, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subs.pop(key, None)

    def publish(self, event: IngestionEvent) -> None:
        if not self._redis:
            return
        data = event.serialize()

        async def _safe_publish(channel: str) -> None:
            try:
                await self._redis.publish(channel, data)
            except Exception as e:
                logger.warning("event bus: publish failed", channel=channel, error=str(e))

        asyncio.ensure_future(_safe_publish(f"{CHANNEL_PREFIX}{event.document_id}"))
        if event.collection_name:
            asyncio.ensure_future(
                _safe_publish(f"{CHANNEL_PREFIX}collection:{event.collection_name}")
            )

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
