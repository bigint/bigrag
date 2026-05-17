from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import orjson
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from bigrag.db.engine import session_factory
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.event_bus import SSE_RETRY_MS, event_bus, next_sse_id

HEARTBEAT_SECONDS = 30.0

SnapshotLoader = Callable[[], Awaitable[Any]]
SnapshotDone = Callable[[Any], bool]
SnapshotInterval = Callable[[Any | None], float]


def json_encode(value: Any) -> str:
    return orjson.dumps(jsonable_encoder(value)).decode()


def event_frame(event: str, data: dict[str, Any]) -> str:
    return (
        f"id: {next_sse_id()}\nretry: {SSE_RETRY_MS}\nevent: {event}\ndata: {json_encode(data)}\n\n"
    )


def snapshot_frame(topic: str, payload: Any) -> str:
    return event_frame(
        "snapshot",
        {
            "topic": topic,
            "payload": payload,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )


def error_frame(topic: str, message: str) -> str:
    return event_frame(
        "error",
        {
            "topic": topic,
            "message": message,
        },
    )


def heartbeat() -> str:
    return f"id: {next_sse_id()}\nretry: {SSE_RETRY_MS}\n: heartbeat\n\n"


async def load_frame(topic: str, load: SnapshotLoader) -> tuple[str, Any | None]:
    try:
        payload = await load()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        safe = sanitize_message_text(f"{type(exc).__name__}") or "snapshot error"
        return error_frame(topic, safe), None
    return snapshot_frame(topic, payload), payload


async def interval_stream(
    topic: str,
    load: SnapshotLoader,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
):
    while True:
        frame, payload = await load_frame(topic, load)
        yield frame
        if payload is not None and done is not None and done(payload):
            break
        remaining = max(1.0, interval_for(payload))
        while remaining > 0:
            delay = min(HEARTBEAT_SECONDS, remaining)
            await asyncio.sleep(delay)
            remaining -= delay
            if remaining > 0:
                yield heartbeat()


async def event_stream(
    topic: str,
    load: SnapshotLoader,
    event_key: str,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
):
    queue = event_bus.subscribe(event_key)
    frame, payload = await load_frame(topic, load)
    yield frame
    if payload is not None and done is not None and done(payload):
        event_bus.unsubscribe(event_key, queue)
        return

    last_snapshot = time.monotonic()
    try:
        while True:
            interval = max(1.0, interval_for(payload))
            elapsed = time.monotonic() - last_snapshot
            timeout = min(HEARTBEAT_SECONDS, max(0.1, interval - elapsed))
            try:
                marker = await asyncio.wait_for(queue.get(), timeout=timeout)
            except TimeoutError:
                if time.monotonic() - last_snapshot >= interval:
                    frame, payload = await load_frame(topic, load)
                    last_snapshot = time.monotonic()
                    yield frame
                    if payload is not None and done is not None and done(payload):
                        break
                else:
                    yield heartbeat()
                continue

            frame, payload = await load_frame(topic, load)
            last_snapshot = time.monotonic()
            yield frame
            if marker is None:
                if payload is None or done is None or done(payload):
                    break
                continue
            if payload is not None and done is not None and done(payload):
                break
    finally:
        event_bus.unsubscribe(event_key, queue)


def stream_response(stream) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def interval_response(
    topic: str,
    load: SnapshotLoader,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
) -> StreamingResponse:
    return stream_response(interval_stream(topic, load, interval_for, done))


def event_response(
    topic: str,
    load: SnapshotLoader,
    event_key: str,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
) -> StreamingResponse:
    return stream_response(event_stream(topic, load, event_key, interval_for, done))


async def with_session(load: Callable[[Any], Awaitable[Any]]) -> Any:
    async with session_factory()() as session:
        return await load(session)


def fixed(seconds: float) -> SnapshotInterval:
    return lambda _payload: seconds
