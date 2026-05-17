from __future__ import annotations

import asyncio
import itertools
from collections import OrderedDict
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field

import orjson
import redis.asyncio as aioredis

from bigrag.logging import get_logger

logger = get_logger("bigrag.event_bus")

CHANNEL_PREFIX = "bigrag:events:"
LATEST_PREFIX = "bigrag:progress:"
LATEST_TTL_SECONDS = 7 * 24 * 60 * 60
SUBSCRIBER_QUEUE_SIZE = 256
SSE_RETRY_MS = 5000
COMPLETED_MAX_ENTRIES = 10000

_COMPLETE_MARKER = b'{"_complete":true}'
_sse_id_counter = itertools.count(1)


def next_sse_id() -> int:
    return next(_sse_id_counter)


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
        return (
            f"id: {next_sse_id()}\nretry: {SSE_RETRY_MS}\ndata: {orjson.dumps(data).decode()}\n\n"
        )

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
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener: asyncio.Task | None = None
        self._subs: dict[str, list[asyncio.Queue[IngestionEvent | None]]] = {}
        self._latest: dict[str, IngestionEvent] = {}
        self._completed: OrderedDict[str, None] = OrderedDict()
        self._pending: set[asyncio.Task] = set()

    def _mark_completed(self, key: str) -> None:
        if key in self._completed:
            self._completed.move_to_end(key)
            return
        self._completed[key] = None
        while len(self._completed) > COMPLETED_MAX_ENTRIES:
            self._completed.popitem(last=False)

    def _spawn(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

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
        while True:
            try:
                async for message in self._pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        channel: str = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        key = channel.removeprefix(CHANNEL_PREFIX)
                        if message["data"] == _COMPLETE_MARKER:
                            if key in self._completed:
                                continue
                            self._mark_completed(key)
                            for q in list(self._subs.get(key, [])):
                                self._offer(q, None)
                            continue
                        event = IngestionEvent.deserialize(message["data"])
                        self._latest[event.document_id] = event
                        self._dispatch(key, event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.warning("event bus: bad message", error=str(e))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("event bus: listen loop crashed, reconnecting", error=str(e))
                await asyncio.sleep(1)
                try:
                    if self._pubsub:
                        try:
                            await self._pubsub.aclose()
                        except Exception:
                            pass
                    if self._redis:
                        self._pubsub = self._redis.pubsub()
                        await self._pubsub.psubscribe(f"{CHANNEL_PREFIX}*")
                    logger.info("event bus: listen loop restarted")
                except Exception as reconnect_error:
                    logger.warning(
                        "event bus: reconnect failed",
                        error=str(reconnect_error),
                    )
                    await asyncio.sleep(1)

    def _dispatch(self, channel_key: str, event: IngestionEvent) -> None:

        for q in list(self._subs.get(channel_key, [])):
            self._offer(q, event)
        for q in list(self._subs.get("*", [])):
            self._offer(q, event)

    def subscribe(self, key: str) -> asyncio.Queue[IngestionEvent | None]:
        q: asyncio.Queue[IngestionEvent | None] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subs.setdefault(key, []).append(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(key, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subs.pop(key, None)

    def publish(self, event: IngestionEvent) -> None:
        self._latest[event.document_id] = event
        if not self._redis:
            return
        data = event.serialize()

        async def _safe_publish() -> None:
            try:
                await self._redis.set(
                    f"{LATEST_PREFIX}{event.document_id}",
                    data,
                    ex=LATEST_TTL_SECONDS,
                )
                await self._redis.publish(f"{CHANNEL_PREFIX}{event.document_id}", data)
                if event.collection_name:
                    await self._redis.publish(
                        f"{CHANNEL_PREFIX}collection:{event.collection_name}",
                        data,
                    )
            except Exception as e:
                logger.warning(
                    "event bus: publish failed",
                    document_id=event.document_id,
                    error=str(e),
                )

        self._spawn(_safe_publish())

    def complete(self, document_id: str) -> None:
        if document_id in self._completed:
            return
        self._mark_completed(document_id)
        for q in list(self._subs.get(document_id, [])):
            self._offer(q, None)
        if not self._redis:
            return

        async def _safe_publish() -> None:
            try:
                await self._redis.publish(f"{CHANNEL_PREFIX}{document_id}", _COMPLETE_MARKER)
            except Exception as e:
                logger.warning(
                    "event bus: complete publish failed",
                    document_id=document_id,
                    error=str(e),
                )

        self._spawn(_safe_publish())

    def _offer(self, q: asyncio.Queue[IngestionEvent | None], item: IngestionEvent | None) -> None:
        if item is None:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
            return
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        q.put_nowait(item)

    async def latest(self, document_id: str) -> IngestionEvent | None:
        if self._redis:
            try:
                raw = await self._redis.get(f"{LATEST_PREFIX}{document_id}")
            except Exception as e:
                logger.warning(
                    "event bus: latest lookup failed",
                    document_id=document_id,
                    error=str(e),
                )
            else:
                if raw is not None:
                    try:
                        event = IngestionEvent.deserialize(raw)
                    except Exception as e:
                        logger.warning(
                            "event bus: latest payload invalid",
                            document_id=document_id,
                            error=str(e),
                        )
                    else:
                        self._latest[document_id] = event
                        return event
        return self._latest.get(document_id)

    async def latest_many(self, document_ids: list[str]) -> dict[str, IngestionEvent]:
        if not document_ids:
            return {}

        events: dict[str, IngestionEvent] = {}
        if self._redis:
            try:
                keys = [f"{LATEST_PREFIX}{document_id}" for document_id in document_ids]
                raws = await self._redis.mget(keys)
            except Exception as e:
                logger.warning(
                    "event bus: latest many lookup failed",
                    count=len(document_ids),
                    error=str(e),
                )
            else:
                for document_id, raw in zip(document_ids, raws, strict=False):
                    if raw is None:
                        continue
                    try:
                        event = IngestionEvent.deserialize(raw)
                    except Exception as e:
                        logger.warning(
                            "event bus: latest payload invalid",
                            document_id=document_id,
                            error=str(e),
                        )
                        continue
                    self._latest[document_id] = event
                    events[document_id] = event

        for document_id in document_ids:
            if document_id not in events and document_id in self._latest:
                events[document_id] = self._latest[document_id]
        return events

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
