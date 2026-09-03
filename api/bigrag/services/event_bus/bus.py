from __future__ import annotations

import asyncio
from collections import OrderedDict

import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services.event_bus.types import (
    _COMPLETE_MARKER,
    CHANNEL_PREFIX,
    COMPLETED_MAX_ENTRIES,
    INGESTION_EVENTS_KEY,
    LATEST_PREFIX,
    LATEST_TTL_SECONDS,
    IngestionEvent,
)

logger = get_logger("bigrag.event_bus")

MAX_CONNECTIONS = 50


class EventBus:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener: asyncio.Task | None = None
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
        self._redis = aioredis.from_url(
            redis_url, decode_responses=False, max_connections=MAX_CONNECTIONS
        )
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
                            continue
                        event = IngestionEvent.deserialize(message["data"])
                        self._latest[event.document_id] = event
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
                if event.document_id:
                    await self._redis.publish(f"{CHANNEL_PREFIX}{INGESTION_EVENTS_KEY}", data)
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


event_bus = EventBus()
