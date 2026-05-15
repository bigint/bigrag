from __future__ import annotations

import asyncio
import importlib
import uuid
from types import SimpleNamespace

import httpx
import orjson

from bigrag.services import webhook
from bigrag.services.event_bus import IngestionEvent


class ExecuteRows:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, row_provider=None) -> None:
        self.added = []
        self.executed = []
        self.commits = 0
        self.row_provider = row_provider

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, item) -> None:
        self.added.append(item)

    async def execute(self, stmt):
        self.executed.append(stmt)
        rows = self.row_provider() if self.row_provider else []
        return ExecuteRows(rows)

    async def commit(self) -> None:
        self.commits += 1


class FakeHttpClient:
    def __init__(self, responses=None, exc=None) -> None:
        self.responses = list(responses or [])
        self.exc = exc
        self.posts = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, content=None, headers=None):
        self.posts.append((url, content, headers))
        if self.exc:
            raise self.exc
        return self.responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


def configure_session_factory(monkeypatch, row_provider=None):
    sessions = []

    def outer():
        def inner():
            session = FakeSession(row_provider)
            sessions.append(session)
            return session

        return inner

    monkeypatch.setattr(importlib.import_module("bigrag.db.engine"), "session_factory", outer)
    return sessions


def test_webhook_helpers_payload_and_matching(monkeypatch) -> None:
    monkeypatch.setattr(webhook.secrets, "token_urlsafe", lambda size: "token")
    monkeypatch.setattr(webhook._RNG, "uniform", lambda start, end: 1.5)

    secret = webhook.generate_secret()
    signature = webhook.compute_signature("payload", "secret")
    delay = webhook._jittered_delay(10)

    dispatcher = webhook.WebhookDispatcher()
    payload = dispatcher._build_payload(
        "document.failed",
        IngestionEvent(
            document_id="doc",
            step="failed",
            status="failed",
            message="broken",
            detail={"chunks": 3},
            collection_name="docs",
        ),
        "docs",
    )
    data = orjson.loads(payload)

    assert secret == "whsec_token"
    assert signature.startswith("sha256=")
    assert delay == 11.5
    assert data["event"] == "document.failed"
    assert data["error_message"] == "broken"
    assert webhook._matches_webhook(
        {"active": True, "events": ["document.failed"], "collections": ["docs"]},
        "document.failed",
        "docs",
    )
    assert not webhook._matches_webhook(
        {"active": False, "events": ["document.failed"], "collections": ["docs"]},
        "document.failed",
        "docs",
    )
    assert not webhook._matches_webhook(
        {"active": True, "events": ["document.ready"], "collections": ["docs"]},
        "document.failed",
        "docs",
    )
    assert not webhook._matches_webhook(
        {"active": True, "events": ["document.failed"], "collections": ["other"]},
        "document.failed",
        "docs",
    )


def test_webhook_handle_event_dispatches_matching_webhooks(monkeypatch) -> None:
    async def run() -> None:
        deliveries = []
        dispatcher = webhook.WebhookDispatcher()

        async def get_webhooks():
            return [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "url": "https://example.test",
                    "secret": "secret",
                    "events": ["document.ready"],
                    "collections": ["docs"],
                    "active": True,
                },
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "url": "https://example.test",
                    "secret": "secret",
                    "events": ["document.failed"],
                    "collections": ["docs"],
                    "active": True,
                },
            ]

        async def deliver(webhook_arg, event, payload):
            deliveries.append((webhook_arg["id"], event, payload))

        monkeypatch.setattr(dispatcher, "_get_webhooks", get_webhooks)
        monkeypatch.setattr(dispatcher, "_deliver", deliver)

        await dispatcher._handle_event(
            IngestionEvent(
                document_id="doc",
                step="complete",
                status="complete",
                message="done",
                detail={"chunks": 2},
                collection_name="docs",
            )
        )
        await dispatcher._handle_event(
            IngestionEvent(document_id="doc", step="unknown", status="processing", message="skip")
        )

        assert len(deliveries) == 1
        assert deliveries[0][0] == "11111111-1111-1111-1111-111111111111"
        assert deliveries[0][1] == "document.ready"

    asyncio.run(run())


def test_webhook_deliver_once_and_test_delivery(monkeypatch) -> None:
    async def run() -> None:
        clients = [
            FakeHttpClient([httpx.Response(204)]),
            FakeHttpClient([httpx.Response(500)]),
            FakeHttpClient(exc=RuntimeError("down")),
            FakeHttpClient([httpx.Response(200)]),
        ]

        async def resolve(url):
            if "blocked" in url:
                raise ValueError("blocked")
            return url

        class FakeAsyncClientFactory:
            def __init__(self, **kwargs) -> None:
                self.client = clients.pop(0)

            async def __aenter__(self):
                return await self.client.__aenter__()

            async def __aexit__(self, exc_type, exc, tb):
                return await self.client.__aexit__(exc_type, exc, tb)

        monkeypatch.setattr("bigrag.models.webhook.resolve_and_validate_url", resolve)
        monkeypatch.setattr(webhook.httpx, "AsyncClient", FakeAsyncClientFactory)
        monkeypatch.setattr(webhook, "_delivery_timeout", lambda: 5)
        dispatcher = webhook.WebhookDispatcher()
        base = {"url": "https://example.test", "secret": "secret"}

        delivered = await dispatcher.deliver_once(base, "document.ready", "{}")
        failed_http = await dispatcher.deliver_once(base, "document.ready", "{}")
        failed_error = await dispatcher.deliver_once(base, "document.ready", "{}")
        blocked = await dispatcher.deliver_once(
            {"url": "https://blocked.test", "secret": "secret"},
            "x",
            "{}",
        )
        test_delivery = await dispatcher.deliver_test(base)

        assert delivered == {"status": "delivered", "status_code": 204, "error": None}
        assert failed_http == {"status": "failed", "status_code": 500, "error": "HTTP 500"}
        assert failed_error["status"] == "failed"
        assert failed_error["error"].startswith("RuntimeError")
        assert blocked["error"].startswith("Blocked")
        assert test_delivery["status"] == "delivered"

    asyncio.run(run())


def test_webhook_deliver_success_records_database_updates(monkeypatch) -> None:
    async def run() -> None:
        sessions = []

        def rows():
            delivery = sessions[0].added[0]
            return [
                (
                    delivery,
                    SimpleNamespace(
                        id=delivery.webhook_id,
                        url="https://example.test",
                        secret="secret",
                    ),
                )
            ]

        sessions = configure_session_factory(monkeypatch, rows)
        dispatcher = webhook.WebhookDispatcher()
        dispatcher._client = FakeHttpClient([httpx.Response(202)])

        async def resolve(url):
            return url

        enqueued = []

        monkeypatch.setattr("bigrag.models.webhook.resolve_and_validate_url", resolve)
        monkeypatch.setattr(
            "bigrag.services.jobs.actors.enqueue_webhook_outbox",
            lambda delivery_id=None, delay_seconds=0: enqueued.append(delivery_id),
        )
        monkeypatch.setattr(webhook, "_retry_delays", lambda: [0])

        await dispatcher._deliver(
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "url": "https://example.test",
                "secret": "secret",
            },
            "document.ready",
            '{"event":"document.ready"}',
        )
        await dispatcher.process_due_deliveries(limit=1)

        assert len(sessions) == 3
        assert enqueued == [str(sessions[0].added[0].id)]
        assert sessions[0].added
        assert sessions[0].commits == 1
        assert sessions[1].executed
        assert sessions[1].commits == 1
        assert sessions[2].executed
        assert sessions[2].commits == 1
        assert sessions[0].added[0].attempts == 1
        assert dispatcher._client.posts[0][2]["X-BigRAG-Event"] == "document.ready"

    asyncio.run(run())


def test_webhook_deliver_retries_and_records_failure(monkeypatch) -> None:
    async def run() -> None:
        sessions = []

        def rows():
            delivery = sessions[0].added[0]
            return [
                (
                    delivery,
                    SimpleNamespace(
                        id=delivery.webhook_id,
                        url="https://example.test",
                        secret="secret",
                    ),
                )
            ]

        sessions = configure_session_factory(monkeypatch, rows)
        dispatcher = webhook.WebhookDispatcher()
        dispatcher._client = FakeHttpClient([httpx.Response(500), httpx.Response(500)])

        async def resolve(url):
            return url

        enqueued = []

        monkeypatch.setattr("bigrag.models.webhook.resolve_and_validate_url", resolve)
        monkeypatch.setattr(
            "bigrag.services.jobs.actors.enqueue_webhook_outbox",
            lambda delivery_id=None, delay_seconds=0: enqueued.append(delivery_id),
        )
        monkeypatch.setattr(webhook, "_retry_delays", lambda: [0])
        monkeypatch.setattr(webhook, "_jittered_delay", lambda delay: 0)

        await dispatcher._deliver(
            {
                "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
                "url": "https://example.test",
                "secret": "secret",
            },
            "document.ready",
            '{"event":"document.ready"}',
        )
        await dispatcher.process_due_deliveries(limit=1)
        await dispatcher.process_due_deliveries(limit=1)

        assert len(dispatcher._client.posts) == 2
        assert enqueued == [str(sessions[0].added[0].id)]
        assert len(sessions) == 5
        assert sessions[0].added[0].attempts == 2
        assert sessions[-1].executed
        assert sessions[-1].commits == 1

    asyncio.run(run())
