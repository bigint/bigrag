from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from bigrag.services import crypto, embedding_cache


@pytest.fixture(autouse=True)
def reset_crypto() -> None:
    crypto.configure(None)
    yield
    crypto.configure(None)


def test_embedding_cache_encrypts_vectors_when_key_is_configured() -> None:
    crypto.configure(Fernet.generate_key().decode())
    vector = [0.1, -0.2, 3.5]

    blob = embedding_cache._encode_vector(vector)
    decoded = embedding_cache._decode_vector(blob, 3)

    assert blob.startswith(b"gAAAA")
    assert blob != embedding_cache._pack(vector)
    assert decoded == pytest.approx(vector)


def test_embedding_cache_rejects_plaintext_vectors() -> None:
    vector = [0.1, -0.2, 3.5]

    decoded = embedding_cache._decode_vector(embedding_cache._pack(vector), 3)

    assert decoded is None


def test_embedding_cache_skips_corrupt_ciphertext() -> None:
    crypto.configure(Fernet.generate_key().decode())

    decoded = embedding_cache._decode_vector(b"gAAAAbad", 3)

    assert decoded is None


def test_embedding_cache_disabled_mode_turns_cache_off(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "disabled"}

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)

    assert asyncio.run(embedding_cache._cache_enabled()) is False


def test_embedding_cache_without_key_turns_cache_off(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "encrypted"}

    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)

    assert asyncio.run(embedding_cache._cache_enabled()) is False


class CacheSessionContext:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class CacheSession:
    def __init__(self, results=None, rowcount=0, fail=False) -> None:
        self.results = list(results or [])
        self.rowcount = rowcount
        self.fail = fail
        self.executed = []
        self.commits = 0

    async def execute(self, stmt):
        self.executed.append(stmt)
        if self.fail:
            raise RuntimeError("db down")
        if self.results:
            rows = self.results.pop(0)
            return SimpleNamespace(all=lambda: rows, rowcount=self.rowcount)
        return SimpleNamespace(all=lambda: [], rowcount=self.rowcount)

    async def commit(self):
        self.commits += 1


def patch_cache_session(monkeypatch, session: CacheSession) -> None:
    monkeypatch.setattr(
        embedding_cache,
        "session_factory",
        lambda: lambda: CacheSessionContext(session),
    )


def test_embedding_cache_get_many_reads_hits_and_updates_last_hit(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "encrypted"}

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)
    encrypted = embedding_cache._encode_vector([0.25, 0.5])
    session = CacheSession(
        [
            [
                SimpleNamespace(content_hash=embedding_cache._hash("hit"), vector=encrypted),
                SimpleNamespace(
                    content_hash=embedding_cache._hash("plain"),
                    vector=embedding_cache._pack([1.0, 2.0]),
                ),
            ],
            [],
        ]
    )
    patch_cache_session(monkeypatch, session)

    found = asyncio.run(embedding_cache.get_many(["hit", "miss", "plain"], "openai", "model", 2))

    assert found == {0: pytest.approx([0.25, 0.5])}
    assert len(session.executed) == 2
    assert session.commits == 1


def test_embedding_cache_get_many_skips_empty_disabled_and_db_errors(monkeypatch) -> None:
    async def disabled_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "disabled"}

    async def failing_get_values(_keys: list[str]) -> dict[str, str]:
        raise RuntimeError("settings down")

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", disabled_get_values)
    assert asyncio.run(embedding_cache.get_many([], "openai", "model", 2)) == {}
    assert asyncio.run(embedding_cache.get_many(["text"], "openai", "model", 2)) == {}

    monkeypatch.setattr(embedding_cache, "get_values", failing_get_values)
    assert asyncio.run(embedding_cache._cache_enabled()) is False

    monkeypatch.setattr(embedding_cache, "get_values", disabled_get_values)
    session = CacheSession(fail=True)
    patch_cache_session(monkeypatch, session)
    assert asyncio.run(embedding_cache.get_many(["text"], "openai", "model", 2)) == {}


def test_embedding_cache_put_many_writes_when_enabled(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "encrypted"}

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)
    session = CacheSession()
    patch_cache_session(monkeypatch, session)

    async def run() -> None:
        await embedding_cache.put_many(["a"], [[0.1, 0.2]], "openai", "model", 2)
        await embedding_cache.put_many([], [], "openai", "model", 2)
        await embedding_cache.put_many(["a"], [], "openai", "model", 2)

    asyncio.run(run())

    assert len(session.executed) == 1
    assert session.commits == 1


def test_embedding_cache_put_many_ignores_db_errors(monkeypatch) -> None:
    async def fake_get_values(keys: list[str]) -> dict[str, str]:
        return {keys[0]: "encrypted"}

    crypto.configure(Fernet.generate_key().decode())
    monkeypatch.setattr(embedding_cache, "get_values", fake_get_values)
    session = CacheSession(fail=True)
    patch_cache_session(monkeypatch, session)

    asyncio.run(embedding_cache.put_many(["a"], [[0.1]], "openai", "model", 1))

    assert session.commits == 0


def test_embedding_cache_purge_counts_and_failure_paths(monkeypatch) -> None:
    session = CacheSession(rowcount=3)
    patch_cache_session(monkeypatch, session)

    async def run() -> None:
        assert await embedding_cache.purge_all() == 3
        assert await embedding_cache.purge_stale(30) == 3
        assert await embedding_cache.purge_stale(0) == 3

    asyncio.run(run())
    assert session.commits == 3

    failing = CacheSession(fail=True)
    patch_cache_session(monkeypatch, failing)

    async def fail_run() -> None:
        assert await embedding_cache.purge_all() == 0
        assert await embedding_cache.purge_stale(30) == 0

    asyncio.run(fail_run())
