from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bigrag.routers import admin_realtime


def _client(monkeypatch, user=None) -> TestClient:
    app = FastAPI()
    if user is None:
        user = {
            "id": "00000000-0000-0000-0000-000000000001",
            "email": "admin@example.com",
            "role": "admin",
            "auth_method": "session",
        }
    app.dependency_overrides[admin_realtime.require_admin_session] = lambda: user
    app.include_router(admin_realtime.router)

    async def fake_with_session(load):
        return await load(object())

    monkeypatch.setattr(admin_realtime, "_with_session", fake_with_session)
    return TestClient(app)


def _finite_streams(monkeypatch) -> None:
    async def fake_interval_stream(topic, load, interval_for, done=None):
        frame, _ = await admin_realtime._load_frame(topic, load)
        yield frame

    async def fake_event_stream(topic, load, event_key, interval_for, done=None):
        frame, _ = await admin_realtime._load_frame(topic, load)
        yield frame

    monkeypatch.setattr(admin_realtime, "_interval_stream", fake_interval_stream)
    monkeypatch.setattr(admin_realtime, "_event_stream", fake_event_stream)


def _fake_loaders(monkeypatch) -> None:
    async def payload(**_kwargs):
        return {"ok": True}

    async def usage_payload(window_days, **_kwargs):
        return {
            "window_days": window_days,
            "queries_total": 0,
            "queries_per_day_avg": 0,
            "documents_total": 0,
            "chunks_total": 0,
            "storage_bytes_total": 0,
            "embedding_tokens_total": 0,
            "embedding_cost_usd_estimate": 0,
            "by_collection": [],
        }

    async def readiness_payload(_request):
        return JSONResponse({"status": "ok"})

    for name in (
        "access_overview",
        "batch_get_status",
        "connector_sources",
        "connector_sync_jobs",
        "get_collection_stats",
        "get_document",
        "list_access_logs",
        "list_audit_log",
        "list_documents",
        "platform_stats",
        "upload_session_detail",
    ):
        monkeypatch.setattr(admin_realtime, name, payload)
    monkeypatch.setattr(admin_realtime, "get_usage", usage_payload)
    monkeypatch.setattr(admin_realtime, "readiness", readiness_payload)


@pytest.mark.parametrize(
    "path",
    [
        "/v1/admin/realtime/collections/docs/documents",
        "/v1/admin/realtime/collections/docs/documents/doc-id-1",
        "/v1/admin/realtime/collections/docs/documents/batch-status?document_ids=doc-id-1",
        "/v1/admin/realtime/collections/docs/upload-sessions/session-id-1",
        "/v1/admin/realtime/collections/docs/stats",
        "/v1/admin/realtime/google/sources",
        "/v1/admin/realtime/google/sync-jobs",
        "/v1/admin/realtime/access/overview",
        "/v1/admin/realtime/access/logs",
        "/v1/admin/realtime/audit",
        "/v1/admin/realtime/usage?window_days=7",
        "/v1/admin/realtime/platform/stats",
        "/v1/admin/realtime/platform/readiness",
    ],
)
def test_realtime_routes_return_sse_snapshots(monkeypatch, path) -> None:
    _finite_streams(monkeypatch)
    _fake_loaders(monkeypatch)

    response = _client(monkeypatch).get(path)
    text = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: snapshot" in text


def test_usage_stream_payload_matches_rest_shape(monkeypatch) -> None:
    _finite_streams(monkeypatch)
    _fake_loaders(monkeypatch)

    response = _client(monkeypatch).get("/v1/admin/realtime/usage?window_days=7")

    assert '"topic":"usage:7"' in response.text
    assert '"window_days":7' in response.text


def test_realtime_stream_rejects_non_admin_session(monkeypatch) -> None:
    app = FastAPI()

    def reject():
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[admin_realtime.require_admin_session] = reject
    app.include_router(admin_realtime.router)

    response = TestClient(app).get("/v1/admin/realtime/usage")

    assert response.status_code == 403


def test_batch_stream_done_when_documents_terminal() -> None:
    docs = [
        type("Document", (), {"status": "ready"})(),
        type("Document", (), {"status": "failed"})(),
    ]
    payload = type("Batch", (), {"documents": docs})()

    assert admin_realtime._batch_done(payload) is True


def test_upload_session_stream_done_when_terminal() -> None:
    payload = type("Session", (), {"status": "complete"})()

    assert admin_realtime._upload_session_done(payload) is True


def test_event_stream_emits_snapshot_after_event_bus_message(monkeypatch) -> None:
    class FakeEventBus:
        def __init__(self) -> None:
            self.queue = asyncio.Queue()
            self.unsubscribed = False

        def subscribe(self, key):
            return self.queue

        def unsubscribe(self, key, queue):
            self.unsubscribed = True

    async def run():
        bus = FakeEventBus()
        loads: list[int] = []
        monkeypatch.setattr(admin_realtime, "event_bus", bus)

        async def load():
            loads.append(len(loads) + 1)
            return {"count": loads[-1]}

        stream = admin_realtime._event_stream(
            "topic",
            load,
            "document-id",
            lambda _payload: 60.0,
            lambda payload: payload["count"] == 2,
        )
        first = await anext(stream)
        bus.queue.put_nowait(object())
        second = await anext(stream)

        try:
            await anext(stream)
        except StopAsyncIteration:
            stopped = True
        else:
            stopped = False

        return first, second, stopped, bus.unsubscribed

    first, second, stopped, unsubscribed = asyncio.run(run())

    assert '"count":1' in first
    assert '"count":2' in second
    assert stopped is True
    assert unsubscribed is True
