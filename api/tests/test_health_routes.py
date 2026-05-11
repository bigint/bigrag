from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from conftest import ExecuteRows, row

from bigrag.routers import health


def run(coro):
    return asyncio.run(coro)


class FakeRedisCache:
    def __init__(self, value=None) -> None:
        self.value = value
        self.sets = []

    async def get(self, key):
        return self.value

    async def set(self, key, value, ttl=None):
        self.sets.append((key, value, ttl))


class FakeSession:
    def __init__(self) -> None:
        self.executed = []
        self.scalar_values = [2, 3]

    async def execute(self, stmt):
        self.executed.append(stmt)
        return ExecuteRows(
            [
                row(
                    total=5,
                    total_size=100,
                    total_chunks=12,
                    total_tokens=500,
                    ready=3,
                    pending=1,
                    processing=1,
                    failed=0,
                )
            ]
        )

    async def scalar(self, _stmt):
        return self.scalar_values.pop(0)


class FakeSessionContext:
    def __init__(self, session=None) -> None:
        self.session = session or FakeSession()

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class FakeVectorStore:
    provider = "qdrant"
    client = object()

    def __init__(self) -> None:
        self.checked = False

    async def health_check(self):
        self.checked = True


class FakeRedis:
    def __init__(self) -> None:
        self.pings = 0

    async def ping(self):
        self.pings += 1


class FakeQueue:
    def __init__(self) -> None:
        self._redis = FakeRedis()

    @property
    def stats(self):
        async def get_stats():
            return {"queued": 1, "processing": 2}

        return get_stats()


def fake_request(*, vector_store=None, queue=None):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                vector_store=vector_store or FakeVectorStore(),
                queue=queue or FakeQueue(),
            )
        )
    )


def response_body(response) -> dict:
    return json.loads(response.body.decode())


def test_health_route_returns_version(route_client) -> None:
    response = route_client().get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"]


def test_provider_error_categorization() -> None:
    cases = [
        (RuntimeError("401 invalid_api_key"), "auth_failed"),
        (RuntimeError("quota exceeded"), "rate_limited"),
        (TimeoutError("timed out"), "timeout"),
        (ConnectionError("dns unreachable"), "unreachable"),
        (RuntimeError("other"), "unknown"),
    ]

    assert [health._categorize_provider_error(error) for error, _category in cases] == [
        category for _error, category in cases
    ]


def test_check_embedding_provider_handles_missing_and_cached_targets(monkeypatch) -> None:
    async def no_target():
        return None

    monkeypatch.setattr(health, "_resolve_embedding_target", no_target)

    assert run(health._check_embedding_provider()) == {
        "embedding": False,
        "embedding_error": "no API key configured",
    }

    async def target():
        return ("openai", "text-embedding-3-small", 1536, "sk", None, "settings")

    monkeypatch.setattr(health, "_resolve_embedding_target", target)
    monkeypatch.setattr(
        health,
        "redis_cache",
        FakeRedisCache({"ok": False, "error": "auth_failed"}),
    )

    assert run(health._check_embedding_provider()) == {
        "embedding": False,
        "embedding_source": "settings",
        "embedding_error": "auth_failed",
    }


def test_check_embedding_provider_caches_success_and_failures(monkeypatch) -> None:
    class FakeEmbeddingModel:
        def __init__(self, *, fail=False) -> None:
            self.fail = fail

        async def embed(self, _texts, input_type):
            if self.fail:
                raise RuntimeError("rate limit")
            return [[0.1]]

    async def target():
        return ("openai", "text-embedding-3-small", 1536, "sk", None, "settings")

    cache = FakeRedisCache()
    monkeypatch.setattr(health, "_resolve_embedding_target", target)
    monkeypatch.setattr(health, "redis_cache", cache)
    monkeypatch.setattr(
        "bigrag.services.embedding.get_embedding_model",
        lambda **_kwargs: FakeEmbeddingModel(),
    )

    assert run(health._check_embedding_provider()) == {
        "embedding": True,
        "embedding_source": "settings",
    }
    assert cache.sets == [
        ("health:embedding:openai:settings", {"ok": True}, health._EMBEDDING_HEALTH_TTL)
    ]

    cache = FakeRedisCache()
    monkeypatch.setattr(health, "redis_cache", cache)
    monkeypatch.setattr(
        "bigrag.services.embedding.get_embedding_model",
        lambda **_kwargs: FakeEmbeddingModel(fail=True),
    )

    assert run(health._check_embedding_provider()) == {
        "embedding": False,
        "embedding_error": "rate_limited",
        "embedding_source": "settings",
    }
    assert cache.sets == [
        (
            "health:embedding:openai:settings",
            {"ok": False, "error": "rate_limited"},
            health._EMBEDDING_HEALTH_TTL,
        )
    ]


def test_readiness_reports_ok_and_degraded_states(monkeypatch) -> None:
    async def embedding_ok():
        return {"embedding": True, "embedding_source": "settings"}

    monkeypatch.setattr(health, "session_factory", lambda: lambda: FakeSessionContext())
    monkeypatch.setattr(health, "_check_embedding_provider", embedding_ok)

    response = run(health.readiness(fake_request()))

    assert response.status_code == 200
    assert response_body(response)["status"] == "ok"
    assert response_body(response)["qdrant"] is True

    vector_store = SimpleNamespace(provider="qdrant", client=None)

    response = run(health.readiness(fake_request(vector_store=vector_store)))

    assert response.status_code == 503
    assert response_body(response)["status"] == "degraded"
    assert response_body(response)["vector_store"] is False


def test_platform_stats_uses_cache_and_populates_uncached_result(monkeypatch) -> None:
    cached = {"collections": 9}
    cache = FakeRedisCache(cached)
    monkeypatch.setattr(health, "redis_cache", cache)

    assert run(health.platform_stats(fake_request(), {}, FakeSession())) == cached

    cache = FakeRedisCache()
    monkeypatch.setattr(health, "redis_cache", cache)

    result = run(health.platform_stats(fake_request(), {}, FakeSession()))

    assert result == {
        "collections": 2,
        "documents": {
            "total": 5,
            "ready": 3,
            "pending": 1,
            "processing": 1,
            "failed": 0,
            "total_chunks": 12,
            "total_tokens": 500,
            "total_size_bytes": 100,
        },
        "webhooks": 3,
        "queue": {"queued": 1, "processing": 2},
    }
    assert cache.sets == [("stats:platform", result, 15)]
