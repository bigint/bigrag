from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.event_bus import event_bus
from bigrag.services.realtime import messages
from bigrag.services.realtime.specs import (
    EventTopic,
    RealtimeTopic,
    SnapshotTopic,
)
from bigrag.services.realtime.topics import (
    resolve_topic,
    topic_error_message,
)

HEARTBEAT_SECONDS = 30.0

SendMessage = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class Subscription:
    id: str
    topic: RealtimeTopic
    task: asyncio.Task


class RealtimeConnection:
    def __init__(self, websocket: WebSocket, principal: dict | None) -> None:
        self.websocket = websocket
        self.principal = principal
        self.outgoing: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=1024)
        self.subscriptions: dict[str, Subscription] = {}

    async def run(self) -> None:
        writer = asyncio.create_task(self._write_loop())
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            while True:
                raw = await self.websocket.receive_text()
                await self._handle_raw(raw)
        except WebSocketDisconnect:
            pass
        finally:
            await self.close()
            heartbeat.cancel()
            writer.cancel()
            await asyncio.gather(heartbeat, writer, return_exceptions=True)

    async def close(self) -> None:
        for subscription_id in list(self.subscriptions):
            await self.unsubscribe(subscription_id, notify=False)
        await self.outgoing.put(None)

    async def send(self, message: dict[str, Any]) -> None:
        await self.outgoing.put(message)

    async def _write_loop(self) -> None:
        while True:
            message = await self.outgoing.get()
            if message is None:
                return
            await self.websocket.send_json(messages.encode_message(message))

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self.send(messages.heartbeat())

    async def _handle_raw(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(messages.error(None, None, "Invalid JSON message"))
            return
        if not isinstance(message, dict):
            await self.send(messages.error(None, None, "Message must be a JSON object"))
            return
        message_type = message.get("type")
        if message_type == "ping":
            await self.send(messages.pong())
            return
        if message_type == "subscribe":
            await self._subscribe(message)
            return
        if message_type == "unsubscribe":
            subscription_id = _subscription_id(message)
            if subscription_id is None:
                await self.send(messages.error(None, None, "id is required"))
                return
            await self.unsubscribe(subscription_id)
            return
        await self.send(messages.error(None, None, "Unknown realtime message type"))

    async def _subscribe(self, message: dict[str, Any]) -> None:
        subscription_id = _subscription_id(message)
        topic_name = message.get("topic")
        params = message.get("params") or {}
        if subscription_id is None:
            await self.send(messages.error(None, None, "id is required"))
            return
        if not isinstance(topic_name, str) or not topic_name:
            await self.send(messages.error(subscription_id, None, "topic is required"))
            return
        if not isinstance(params, dict):
            await self.send(messages.error(subscription_id, topic_name, "params must be an object"))
            return
        if subscription_id in self.subscriptions:
            await self.unsubscribe(subscription_id, notify=False)
        try:
            topic = await resolve_topic(self.websocket, self.principal, topic_name, params)
        except Exception as exc:
            await self.send(messages.error(subscription_id, topic_name, topic_error_message(exc)))
            return
        task = asyncio.create_task(self._run_subscription(subscription_id, topic))
        self.subscriptions[subscription_id] = Subscription(subscription_id, topic, task)
        await self.send(messages.subscribed(subscription_id, topic.topic))

    async def unsubscribe(self, subscription_id: str, *, notify: bool = True) -> None:
        subscription = self.subscriptions.pop(subscription_id, None)
        if subscription is None:
            return
        subscription.task.cancel()
        await asyncio.gather(subscription.task, return_exceptions=True)
        if notify:
            await self.send(messages.complete(subscription_id, subscription.topic.topic))

    async def _run_subscription(self, subscription_id: str, topic: RealtimeTopic) -> None:
        try:
            if isinstance(topic, SnapshotTopic):
                await run_snapshot_subscription(subscription_id, topic, self.send)
            else:
                await run_event_subscription(subscription_id, topic, self.send)
        finally:
            self.subscriptions.pop(subscription_id, None)


async def run_snapshot_subscription(
    subscription_id: str,
    topic: SnapshotTopic,
    send: SendMessage,
) -> None:
    queue = event_bus.subscribe(topic.event_key) if topic.event_key else None
    payload: Any | None = None
    last_snapshot = 0.0
    try:
        payload = await _load_snapshot(subscription_id, topic, send)
        last_snapshot = time.monotonic()
        if payload is not None and topic.done is not None and topic.done(payload):
            await send(messages.complete(subscription_id, topic.topic))
            return
        while True:
            interval = max(1.0, topic.interval_for(payload))
            if queue is None:
                await asyncio.sleep(interval)
            else:
                elapsed = time.monotonic() - last_snapshot
                timeout = max(0.1, interval - elapsed)
                try:
                    marker = await asyncio.wait_for(queue.get(), timeout=timeout)
                except TimeoutError:
                    marker = object()
                if marker is None and payload is not None and topic.done is not None:
                    if topic.done(payload):
                        await send(messages.complete(subscription_id, topic.topic))
                        return
            payload = await _load_snapshot(subscription_id, topic, send)
            last_snapshot = time.monotonic()
            if payload is not None and topic.done is not None and topic.done(payload):
                await send(messages.complete(subscription_id, topic.topic))
                return
    finally:
        if queue is not None and topic.event_key is not None:
            event_bus.unsubscribe(topic.event_key, queue)


async def run_event_subscription(
    subscription_id: str,
    topic: EventTopic,
    send: SendMessage,
) -> None:
    queue = event_bus.subscribe(topic.event_key)
    try:
        if topic.connected_payload is not None:
            await send(messages.event(subscription_id, topic.topic, topic.connected_payload))
        while True:
            event = await queue.get()
            if event is None:
                await send(messages.complete(subscription_id, topic.topic))
                return
            await send(
                messages.event(
                    subscription_id,
                    topic.topic,
                    {
                        "document_id": event.document_id,
                        "step": event.step,
                        "status": event.status,
                        "message": event.message,
                        "progress": event.progress,
                        **event.detail,
                    },
                )
            )
    finally:
        event_bus.unsubscribe(topic.event_key, queue)


async def _load_snapshot(
    subscription_id: str,
    topic: SnapshotTopic,
    send: SendMessage,
) -> Any | None:
    try:
        payload = await topic.load()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        message = _load_error_message(exc)
        await send(messages.error(subscription_id, topic.topic, message))
        return None
    await send(messages.snapshot(subscription_id, topic.topic, payload))
    return payload


def _load_error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        return detail
    return sanitize_message_text(f"{type(exc).__name__}") or "snapshot error"


def _subscription_id(message: dict[str, Any]) -> str | None:
    value = message.get("id")
    if isinstance(value, str) and value:
        return value
    return None
