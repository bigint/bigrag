from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from websockets.asyncio.client import connect

from bigrag.types.realtime import RealtimeMessage


class RealtimeConnection:
    def __init__(self, client) -> None:
        self._client = client
        self._socket = None
        self._reader: asyncio.Task | None = None
        self._queues: dict[str, asyncio.Queue[RealtimeMessage | None]] = {}

    async def connect(self) -> None:
        if self._socket is not None:
            return
        self._socket = await connect(
            _realtime_url(self._client.base_url),
            additional_headers=self._client._headers(),
            open_timeout=self._client.timeout,
        )
        self._reader = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        for queue in self._queues.values():
            queue.put_nowait(None)
        self._queues.clear()
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
            self._reader = None
        if self._socket is not None:
            await self._socket.close()
            self._socket = None

    async def subscribe(
        self, topic: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[RealtimeMessage, None]:
        await self.connect()
        subscription_id = uuid4().hex
        queue: asyncio.Queue[RealtimeMessage | None] = asyncio.Queue()
        self._queues[subscription_id] = queue
        await self._send(
            {
                "type": "subscribe",
                "id": subscription_id,
                "topic": topic,
                "params": _compact_params(params or {}),
            }
        )
        try:
            while True:
                message = await queue.get()
                if message is None:
                    return
                yield message
                if message.get("type") == "complete":
                    return
        finally:
            await self._send({"type": "unsubscribe", "id": subscription_id})
            self._queues.pop(subscription_id, None)
            queue.put_nowait(None)

    async def _send(self, message: dict[str, Any]) -> None:
        if self._socket is None:
            return
        await self._socket.send(json.dumps(message))

    async def _read_loop(self) -> None:
        try:
            while True:
                raw = await self._socket.recv()
                if isinstance(raw, bytes):
                    raw = raw.decode()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(message, dict):
                    continue
                if message.get("type") in {"heartbeat", "pong", "subscribed"}:
                    continue
                subscription_id = message.get("id")
                if not isinstance(subscription_id, str):
                    continue
                queue = self._queues.get(subscription_id)
                if queue is not None:
                    queue.put_nowait(message)
        finally:
            for queue in self._queues.values():
                queue.put_nowait(None)


class RealtimeResource:
    def __init__(self, client) -> None:
        self._client = client

    def connect(self) -> RealtimeConnection:
        return RealtimeConnection(self._client)

    async def subscribe(
        self, topic: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[RealtimeMessage, None]:
        connection = self.connect()
        try:
            async for message in connection.subscribe(topic, params):
                yield message
        finally:
            await connection.close()


def _realtime_url(base_url: str) -> str:
    if base_url.startswith("https://"):
        return f"wss://{base_url.removeprefix('https://').rstrip('/')}/v1/realtime"
    if base_url.startswith("http://"):
        return f"ws://{base_url.removeprefix('http://').rstrip('/')}/v1/realtime"
    return f"{base_url.rstrip('/')}/v1/realtime"


def _compact_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}
