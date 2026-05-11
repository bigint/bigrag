from __future__ import annotations

import asyncio

from rag_computer.services.event_bus import EventBus, IngestionEvent


def test_ingestion_event_serialization_and_sse_shape() -> None:
    event = IngestionEvent(
        document_id="doc",
        collection_name="docs",
        step="upload",
        status="processing",
        message="working",
        progress=0.5,
        detail={"count": 2},
    )

    restored = IngestionEvent.deserialize(event.serialize())

    assert restored == event
    assert '"count":2' in event.to_sse()
    assert event.to_sse().startswith("data: ")


def test_event_bus_subscribe_dispatch_complete_and_latest() -> None:
    async def run() -> None:
        bus = EventBus()
        event = IngestionEvent(
            document_id="doc",
            collection_name="docs",
            step="search",
            status="complete",
            message="done",
        )
        direct = bus.subscribe("doc")
        wildcard = bus.subscribe("*")

        bus.publish(event)
        bus._dispatch("doc", event)
        bus.complete("doc")

        assert await direct.get() == event
        assert await direct.get() is None
        assert await wildcard.get() == event
        assert await bus.latest("doc") == event

        bus.unsubscribe("doc", direct)
        bus.unsubscribe("*", wildcard)
        assert bus._subs == {}

    asyncio.run(run())


def test_event_bus_stream_unsubscribes_when_complete() -> None:
    async def run() -> None:
        bus = EventBus()
        event = IngestionEvent(
            document_id="doc",
            step="step",
            status="processing",
            message="message",
        )
        stream = bus.stream("doc")
        first = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        bus._dispatch("doc", event)
        bus.complete("doc")

        assert await first == event
        try:
            await anext(stream)
        except StopAsyncIteration:
            pass
        else:
            raise AssertionError("expected stream to finish")
        assert bus._subs == {}

    asyncio.run(run())
