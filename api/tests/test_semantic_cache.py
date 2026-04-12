"""Tests for the semantic query cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from bigrag.services import semantic_cache


class _FakeRedis:
    """Minimal in-memory Redis stand-in (lpush/lrange/ltrim/delete/expire)."""

    def __init__(self):
        self.lists: dict[str, list[bytes]] = {}

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        if end == -1:
            end = len(lst) - 1
        return lst[start : end + 1]

    async def ltrim(self, key, start, end):
        if key in self.lists:
            if end == -1:
                end = len(self.lists[key]) - 1
            self.lists[key] = self.lists[key][start : end + 1]

    async def delete(self, key):
        self.lists.pop(key, None)

    async def expire(self, key, ttl):
        pass  # no-op for tests


@pytest.fixture
def fake_redis():
    fake = _FakeRedis()
    with patch("bigrag.services.semantic_cache.redis_cache._redis", fake):
        yield fake


class TestLookup:
    @pytest.mark.asyncio
    async def test_empty_cache_returns_none(self, fake_redis):
        assert await semantic_cache.lookup("coll", [1.0, 0.0]) is None

    @pytest.mark.asyncio
    async def test_exact_match_above_threshold(self, fake_redis):
        await semantic_cache.store("coll", [1.0, 0.0], {"results": ["stored"]})
        hit = await semantic_cache.lookup("coll", [1.0, 0.0])
        assert hit == {"results": ["stored"]}

    @pytest.mark.asyncio
    async def test_orthogonal_query_misses(self, fake_redis):
        await semantic_cache.store("coll", [1.0, 0.0], {"results": ["stored"]})
        miss = await semantic_cache.lookup("coll", [0.0, 1.0])
        assert miss is None

    @pytest.mark.asyncio
    async def test_near_match_above_threshold(self, fake_redis):
        await semantic_cache.store("coll", [1.0, 0.0], {"results": ["stored"]})
        # cosine([1,0], [0.99, 0.01]) ≈ 0.9999 → above 0.97
        hit = await semantic_cache.lookup("coll", [0.99, 0.01])
        assert hit is not None

    @pytest.mark.asyncio
    async def test_scoped_by_collection(self, fake_redis):
        await semantic_cache.store("coll_a", [1.0, 0.0], {"results": ["a"]})
        miss = await semantic_cache.lookup("coll_b", [1.0, 0.0])
        assert miss is None

    @pytest.mark.asyncio
    async def test_missing_redis_returns_none(self):
        with patch("bigrag.services.semantic_cache.redis_cache._redis", None):
            assert await semantic_cache.lookup("coll", [1.0]) is None


class TestStore:
    @pytest.mark.asyncio
    async def test_store_trims_to_max_entries(self, fake_redis):
        # Force many writes and assert the list stays bounded.
        for i in range(semantic_cache.MAX_ENTRIES_PER_COLLECTION + 50):
            await semantic_cache.store("coll", [1.0, float(i)], {"i": i})
        entries = fake_redis.lists[semantic_cache._list_key("coll")]
        assert len(entries) <= semantic_cache.MAX_ENTRIES_PER_COLLECTION

    @pytest.mark.asyncio
    async def test_invalidate_drops_list(self, fake_redis):
        await semantic_cache.store("coll", [1.0], {"x": 1})
        await semantic_cache.invalidate("coll")
        assert await semantic_cache.lookup("coll", [1.0]) is None


@pytest.mark.asyncio
async def test_ttl_expires_old_entries(fake_redis):
    # Seed a pre-aged entry by writing directly.
    expired = orjson.dumps(
        {"vec": [1.0], "payload": {"old": True}, "ts": 0.0}
    )
    await fake_redis.lpush(semantic_cache._list_key("coll"), expired)

    hit = await semantic_cache.lookup("coll", [1.0])
    assert hit is None
