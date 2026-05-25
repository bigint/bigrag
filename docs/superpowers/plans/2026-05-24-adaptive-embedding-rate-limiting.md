# Adaptive Embedding Rate Limiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-process, reactive embedding rate-limit handling with a single Redis-coordinated, self-tuning (AIMD) concurrency limiter so the 5 workers stop blasting the provider in lockstep and 429s become rare.

**Architecture:** A new `embedding_gate` async context manager wraps every provider HTTP call. It (1) waits out any active Redis 429 cooldown, (2) acquires a permit from a shared, dynamically-sized concurrency limit stored in Redis, (3) on success nudges the limit up toward the `embedding_concurrency` ceiling, and (4) on a 429 halves the limit and records the cooldown. The limit lives in Redis (a ZSET of leased permits plus a float limit key), with a process-local fallback when Redis is absent. The previously per-process semaphores and the duplicated cooldown logic in each provider are removed.

**Tech Stack:** Python 3.12, asyncio, `redis.asyncio` (Lua via `register_script`), structlog. No new dependencies. Lint via `api/.venv/bin/ruff` (pre-commit also runs ruff/biome on commit). No unit-test framework exists in this repo — verification is ruff + the existing load test (`tests/load`).

**Conventions (from user):** Conventional commit messages (`feat: ...`, not `feat(scope): ...`). **No co-author trailer.** **No explanatory comments in code** — the diff must speak for itself. Commit + push after each task.

**Key bounds:**
- Ceiling = `sync_value("embedding_concurrency")` clamped to `>= 1` (now global across workers, was per-process).
- `MIN_LIMIT = 1.0`, `DECREASE_GUARD_MS = 1000`, `ACQUIRE_RETRY_MIN_MS = 25`, `ACQUIRE_RETRY_MAX_MS = 100`, `LEASE_SECONDS = 60`, `LIMIT_TTL_MS = 3_600_000`.
- The Redis client uses `decode_responses=False` (`redis_cache.py:22`), and Lua numeric returns truncate to int — so the limit-math scripts `return tostring(limit)` and Python parses the returned **bytes** back to `float` via `float(raw.decode())`.

---

### Task 1: Create the `embedding_gate` module

**Files:**
- Create: `api/bigrag/services/embedding_gate.py`

- [ ] **Step 1: Write the module**

Create `api/bigrag/services/embedding_gate.py` with exactly this content:

```python
from __future__ import annotations

import asyncio
import hashlib
import random
import time
import uuid
from contextlib import asynccontextmanager

from bigrag.logging import get_logger
from bigrag.services import redis_cache
from bigrag.services.embedding_rate_limit import (
    RATE_LIMIT_COOLDOWN_KEY_PREFIX,
    is_rate_limit_error,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)

logger = get_logger("bigrag.embedding_gate")

MIN_LIMIT = 1.0
DECREASE_GUARD_MS = 1000
ACQUIRE_RETRY_MIN_MS = 25
ACQUIRE_RETRY_MAX_MS = 100
LEASE_SECONDS = 60
LIMIT_TTL_MS = 3_600_000

INFLIGHT_PREFIX = "bigrag:embedding:inflight:"
LIMIT_PREFIX = "bigrag:embedding:limit:"
LIMIT_DEC_PREFIX = "bigrag:embedding:limit-dec:"

_LOCAL_TOKEN = "__local__"
_FAILOPEN_TOKEN = "__failopen__"

_ACQUIRE_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local limit = tonumber(redis.call('GET', KEYS[2]))
if limit == nil then limit = tonumber(ARGV[4]); redis.call('SET', KEYS[2], limit, 'PX', ARGV[6]) end
local count = redis.call('ZCARD', KEYS[1])
if count < math.floor(limit) then
  redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
  redis.call('PEXPIRE', KEYS[1], ARGV[5])
  return 1
end
return 0
"""

_SUCCESS_LUA = """
local limit = tonumber(redis.call('GET', KEYS[1]))
if limit == nil then limit = tonumber(ARGV[1]) end
limit = limit + 1.0 / limit
if limit > tonumber(ARGV[1]) then limit = tonumber(ARGV[1]) end
redis.call('SET', KEYS[1], limit, 'PX', ARGV[2])
return tostring(limit)
"""

_DECREASE_LUA = """
local last = tonumber(redis.call('GET', KEYS[2])) or 0
local limit = tonumber(redis.call('GET', KEYS[1]))
if limit == nil then limit = tonumber(ARGV[2]) end
if tonumber(ARGV[1]) - last > tonumber(ARGV[4]) then
  limit = limit * 0.5
  if limit < tonumber(ARGV[3]) then limit = tonumber(ARGV[3]) end
  redis.call('SET', KEYS[1], limit, 'PX', ARGV[5])
  redis.call('SET', KEYS[2], ARGV[1], 'PX', ARGV[5])
end
return tostring(limit)
"""


class _LocalLimiter:
    def __init__(self, ceiling: float) -> None:
        self.limit = ceiling
        self.inflight = 0
        self.last_decrease = 0.0
        self.cond = asyncio.Condition()

    async def acquire(self) -> None:
        async with self.cond:
            while self.inflight >= int(self.limit):
                await self.cond.wait()
            self.inflight += 1

    async def release(self) -> None:
        async with self.cond:
            self.inflight = max(0, self.inflight - 1)
            self.cond.notify(1)

    async def on_success(self, ceiling: float) -> float:
        async with self.cond:
            self.limit = min(self.limit + 1.0 / self.limit, ceiling)
            self.cond.notify(1)
            return self.limit

    async def on_rate_limited(self) -> float:
        async with self.cond:
            now = time.monotonic()
            if now - self.last_decrease > DECREASE_GUARD_MS / 1000:
                self.limit = max(self.limit * 0.5, MIN_LIMIT)
                self.last_decrease = now
            return self.limit


_local_limiters: dict[str, _LocalLimiter] = {}
_scripts: dict[str, tuple] = {}


def _ceiling() -> float:
    from bigrag.services.runtime_settings import sync_value

    return max(float(sync_value("embedding_concurrency")), MIN_LIMIT)


def _digest(cache_identity: str) -> str:
    return hashlib.sha256(str(cache_identity).encode()).hexdigest()[:24]


def _local(digest: str) -> _LocalLimiter:
    limiter = _local_limiters.get(digest)
    if limiter is None:
        limiter = _LocalLimiter(_ceiling())
        _local_limiters[digest] = limiter
    return limiter


def _script(redis, name: str, body: str):
    cached = _scripts.get(name)
    if cached is not None and cached[0] is redis:
        return cached[1]
    script = redis.register_script(body)
    _scripts[name] = (redis, script)
    return script


def _as_float(raw) -> float:
    if isinstance(raw, (bytes, bytearray)):
        return float(raw.decode())
    return float(raw)


def reset_embedding_limiters() -> None:
    _local_limiters.clear()


async def _acquire(redis, digest: str) -> str:
    if redis is None:
        await _local(digest).acquire()
        return _LOCAL_TOKEN
    inflight_key = INFLIGHT_PREFIX + digest
    limit_key = LIMIT_PREFIX + digest
    ceiling = _ceiling()
    script = _script(redis, "acquire", _ACQUIRE_LUA)
    while True:
        token = uuid.uuid4().hex
        now_ms = int(time.time() * 1000)
        try:
            ok = await script(
                keys=[inflight_key, limit_key],
                args=[
                    now_ms,
                    now_ms + LEASE_SECONDS * 1000,
                    token,
                    ceiling,
                    LEASE_SECONDS * 1000 * 2,
                    LIMIT_TTL_MS,
                ],
            )
        except Exception as exc:
            logger.debug("embedding gate acquire fell back", error=repr(exc))
            return _FAILOPEN_TOKEN
        if int(ok) == 1:
            return token
        await asyncio.sleep(random.uniform(ACQUIRE_RETRY_MIN_MS, ACQUIRE_RETRY_MAX_MS) / 1000)


async def _release(redis, digest: str, token: str) -> None:
    if token == _LOCAL_TOKEN:
        await _local(digest).release()
        return
    if token == _FAILOPEN_TOKEN or redis is None:
        return
    try:
        await redis.zrem(INFLIGHT_PREFIX + digest, token)
    except Exception as exc:
        logger.debug("embedding gate release failed", error=repr(exc))


async def _on_success(redis, digest: str) -> None:
    if redis is None:
        await _local(digest).on_success(_ceiling())
        return
    try:
        script = _script(redis, "success", _SUCCESS_LUA)
        await script(keys=[LIMIT_PREFIX + digest], args=[_ceiling(), LIMIT_TTL_MS])
    except Exception as exc:
        logger.debug("embedding gate success update failed", error=repr(exc))


async def _on_rate_limited(
    redis, digest: str, cooldown_key: str, exc: Exception, provider: str, model_name: str
) -> None:
    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
    if redis is None:
        new_limit = await _local(digest).on_rate_limited()
    else:
        try:
            script = _script(redis, "decrease", _DECREASE_LUA)
            now_ms = int(time.time() * 1000)
            raw = await script(
                keys=[LIMIT_PREFIX + digest, LIMIT_DEC_PREFIX + digest],
                args=[now_ms, _ceiling(), MIN_LIMIT, DECREASE_GUARD_MS, LIMIT_TTL_MS],
            )
            new_limit = _as_float(raw)
        except Exception as update_exc:
            logger.debug("embedding gate decrease failed", error=repr(update_exc))
            return
    logger.warning(
        "embedding limit decreased",
        provider=provider,
        model=model_name,
        new_limit=round(new_limit, 2),
    )


@asynccontextmanager
async def embedding_gate(cache_identity: str, provider: str, model_name: str):
    digest = _digest(cache_identity)
    cooldown_key = RATE_LIMIT_COOLDOWN_KEY_PREFIX + digest
    await wait_for_rate_limit_cooldown(cooldown_key, provider, model_name)
    redis = redis_cache.get_redis()
    token = await _acquire(redis, digest)
    err: Exception | None = None
    try:
        yield
    except Exception as exc:
        err = exc
        raise
    finally:
        await _release(redis, digest, token)
        if err is None:
            await _on_success(redis, digest)
        elif is_rate_limit_error(err):
            await _on_rate_limited(redis, digest, cooldown_key, err, provider, model_name)
```

- [ ] **Step 2: Lint the new module**

Run: `api/.venv/bin/ruff check api/bigrag/services/embedding_gate.py`
Expected: `All checks passed!`

- [ ] **Step 3: Import smoke test**

Run: `api/.venv/bin/python -c "import bigrag.services.embedding_gate as g; print(g.embedding_gate, g.reset_embedding_limiters)"`
Expected: prints the two function objects, no traceback. (If it fails due to missing env/settings, note it and rely on ruff — the module has no import-time side effects beyond importing `redis_cache`.)

- [ ] **Step 4: Commit**

```bash
git add api/bigrag/services/embedding_gate.py
git commit -m "feat: add adaptive embedding rate-limit gate"
```

---

### Task 2: Route all three providers through the gate

**Files:**
- Modify: `api/bigrag/services/embedding/openai.py:1-13,46,93-118`
- Modify: `api/bigrag/services/embedding/cohere.py:1-13,38,68-95`
- Modify: `api/bigrag/services/embedding/voyage.py:1-15,42,92-142`

- [ ] **Step 1: Update `openai.py` imports**

Replace `api/bigrag/services/embedding/openai.py:6-13`:

```python
from bigrag.services.embedding.base import EmbeddingModel, get_semaphore, logger, truncate_to_tokens
from bigrag.services.embedding_rate_limit import (
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)
```

with:

```python
from bigrag.services.embedding.base import EmbeddingModel, logger, truncate_to_tokens
from bigrag.services.embedding_gate import embedding_gate
```

- [ ] **Step 2: Delete the unused semaphore-key line in `openai.py`**

Delete `api/bigrag/services/embedding/openai.py:46`:

```python
        self._semaphore_key = f"openai:{self._base_url or 'default'}"
```

- [ ] **Step 3: Replace `openai.py` `_embed_single`**

Replace `api/bigrag/services/embedding/openai.py:93-118`:

```python
    async def _embed_single(self, texts: list[str]) -> list[list[float]]:
        cooldown_key = rate_limit_cooldown_key(
            self._cache_identity, self.provider, self._model_name, self._dimension
        )
        kwargs: dict = {"input": texts, "model": self._model_name}
        if self._supports_dimensions(self._model_name):
            kwargs["dimensions"] = self._dimension
        async with await get_semaphore(self._semaphore_key):
            await wait_for_rate_limit_cooldown(cooldown_key, self.provider, self._model_name)
            try:
                response = await asyncio.wait_for(
                    self._client.embeddings.create(**kwargs),
                    timeout=60,
                )
            except Exception as exc:
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise
        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"openai returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

with:

```python
    async def _embed_single(self, texts: list[str]) -> list[list[float]]:
        kwargs: dict = {"input": texts, "model": self._model_name}
        if self._supports_dimensions(self._model_name):
            kwargs["dimensions"] = self._dimension
        async with embedding_gate(self._cache_identity, self.provider, self._model_name):
            response = await asyncio.wait_for(
                self._client.embeddings.create(**kwargs),
                timeout=60,
            )
        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"openai returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

- [ ] **Step 4: Update `cohere.py` imports**

Replace `api/bigrag/services/embedding/cohere.py:5-12`:

```python
from bigrag.services.embedding.base import EmbeddingModel, get_semaphore, logger, truncate_to_tokens
from bigrag.services.embedding_rate_limit import (
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)
```

with:

```python
from bigrag.services.embedding.base import EmbeddingModel, logger, truncate_to_tokens
from bigrag.services.embedding_gate import embedding_gate
```

- [ ] **Step 5: Delete the unused semaphore-key line in `cohere.py`**

Delete `api/bigrag/services/embedding/cohere.py:38`:

```python
        self._semaphore_key = "cohere"
```

- [ ] **Step 6: Replace `cohere.py` `_embed_single`**

Replace `api/bigrag/services/embedding/cohere.py:68-95`:

```python
    async def _embed_single(self, texts: list[str], cohere_input_type: str) -> list[list[float]]:
        cooldown_key = rate_limit_cooldown_key(
            self._cache_identity, self.provider, self._model_name, self._dimension
        )
        async with await get_semaphore(self._semaphore_key):
            await wait_for_rate_limit_cooldown(cooldown_key, self.provider, self._model_name)
            try:
                response = await asyncio.wait_for(
                    self._client.embed(
                        texts=texts,
                        model=self._model_name,
                        input_type=cohere_input_type,
                        embedding_types=["float"],
                    ),
                    timeout=60,
                )
            except Exception as exc:
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise
        vectors = [list(e) for e in response.embeddings.float_]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"cohere returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

with:

```python
    async def _embed_single(self, texts: list[str], cohere_input_type: str) -> list[list[float]]:
        async with embedding_gate(self._cache_identity, self.provider, self._model_name):
            response = await asyncio.wait_for(
                self._client.embed(
                    texts=texts,
                    model=self._model_name,
                    input_type=cohere_input_type,
                    embedding_types=["float"],
                ),
                timeout=60,
            )
        vectors = [list(e) for e in response.embeddings.float_]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"cohere returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

- [ ] **Step 7: Update `voyage.py` imports**

Replace `api/bigrag/services/embedding/voyage.py:7-14`:

```python
from bigrag.services.embedding.base import EmbeddingModel, get_semaphore, logger, truncate_to_tokens
from bigrag.services.embedding_rate_limit import (
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)
```

with (all `embedding_rate_limit` imports are dropped — Voyage no longer records cooldowns itself; the gate inspects the raised `VoyageHTTPError` and handles the 429):

```python
from bigrag.services.embedding.base import EmbeddingModel, logger, truncate_to_tokens
from bigrag.services.embedding_gate import embedding_gate
```

- [ ] **Step 8: Delete the unused semaphore-key line in `voyage.py`**

Delete `api/bigrag/services/embedding/voyage.py:42`:

```python
        self._semaphore_key = "voyage"
```

- [ ] **Step 9: Replace `voyage.py` `_embed_single`**

Replace `api/bigrag/services/embedding/voyage.py:92-142`:

```python
    async def _embed_single(self, texts: list[str], voyage_input_type: str) -> list[list[float]]:
        payload = {
            "input": texts,
            "model": self._model_name,
            "input_type": voyage_input_type,
            "output_dimension": self._dimension,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        cooldown_key = rate_limit_cooldown_key(
            self._cache_identity, self.provider, self._model_name, self._dimension
        )
        client = await self._get_client()
        async with await get_semaphore(self._semaphore_key):
            await wait_for_rate_limit_cooldown(cooldown_key, self.provider, self._model_name)
            try:
                response = await client.post(
                    f"{self._DEFAULT_BASE_URL}{self._EMBEDDINGS_PATH}",
                    json=payload,
                    headers=headers,
                )
            except Exception as exc:
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise
            if response.status_code >= 400:
                logger.warning(
                    "voyage embed http error",
                    status=response.status_code,
                    body_preview=response.text[:500],
                    model=self._model_name,
                )
                exc = VoyageHTTPError(
                    response.status_code,
                    f"Voyage embed failed ({response.status_code})",
                )
                exc.headers = response.headers
                if is_rate_limit_error(exc):
                    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
                raise exc
        data = response.json()
        vectors = [item["embedding"] for item in data["data"]]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"voyage returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

with:

```python
    async def _embed_single(self, texts: list[str], voyage_input_type: str) -> list[list[float]]:
        payload = {
            "input": texts,
            "model": self._model_name,
            "input_type": voyage_input_type,
            "output_dimension": self._dimension,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = await self._get_client()
        async with embedding_gate(self._cache_identity, self.provider, self._model_name):
            response = await client.post(
                f"{self._DEFAULT_BASE_URL}{self._EMBEDDINGS_PATH}",
                json=payload,
                headers=headers,
            )
            if response.status_code >= 400:
                logger.warning(
                    "voyage embed http error",
                    status=response.status_code,
                    body_preview=response.text[:500],
                    model=self._model_name,
                )
                exc = VoyageHTTPError(
                    response.status_code,
                    f"Voyage embed failed ({response.status_code})",
                )
                exc.headers = response.headers
                raise exc
        data = response.json()
        vectors = [item["embedding"] for item in data["data"]]
        for vector in vectors:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"voyage returned vector of length {len(vector)}, "
                    f"expected {self._dimension} for model {self._model_name}"
                )
        return vectors
```

Why this is correct: the `VoyageHTTPError` raised inside the `async with embedding_gate(...)` block propagates through the context manager. The gate's `finally` calls `is_rate_limit_error(err)` on it; because `VoyageHTTPError` carries `.status_code` and `.headers`, a 429 is detected there and the cooldown + AIMD decrease are applied — replacing the manual `record_rate_limit_cooldown` calls removed here.

- [ ] **Step 10: Lint changed providers**

Run: `api/.venv/bin/ruff check api/bigrag/services/embedding/openai.py api/bigrag/services/embedding/cohere.py api/bigrag/services/embedding/voyage.py`
Expected: `All checks passed!` (no unused-import warnings — confirms the imports were trimmed correctly).

- [ ] **Step 11: Commit**

```bash
git add api/bigrag/services/embedding/openai.py api/bigrag/services/embedding/cohere.py api/bigrag/services/embedding/voyage.py
git commit -m "feat: route embedding providers through the adaptive gate"
```

---

### Task 3: Remove the old per-process semaphores

**Files:**
- Modify: `api/bigrag/services/embedding/base.py:1-11,30-42`
- Modify: `api/bigrag/services/embedding/__init__.py:3-7,17-27`
- Modify: `api/bigrag/services/runtime_settings_apply.py:10,77-78`

- [ ] **Step 1: Strip semaphore code from `base.py`**

In `api/bigrag/services/embedding/base.py`, delete:
- the `import asyncio` line (line 3) — becomes unused;
- the module globals `_embed_semaphores` and `_embed_semaphores_lock` (lines 10-11);
- the `get_semaphore` function (lines 30-38);
- the `reset_embedding_semaphores` function (lines 41-42).

After the edit the top of the file reads exactly:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from bigrag.logging import get_logger

logger = get_logger("bigrag.embedding")

_TOKEN_LIMITS: dict[str, int] = {
```

and `truncate_to_tokens` follows directly after the `_TOKEN_LIMITS` dict (nothing between the dict and that function).

- [ ] **Step 2: Update `embedding/__init__.py`**

Replace `api/bigrag/services/embedding/__init__.py:3-7`:

```python
from bigrag.services.embedding.base import (
    EmbeddingModel,
    reset_embedding_semaphores,
    truncate_to_tokens,
)
```

with:

```python
from bigrag.services.embedding.base import (
    EmbeddingModel,
    truncate_to_tokens,
)
from bigrag.services.embedding_gate import reset_embedding_limiters
```

Then in `__all__`, replace `"reset_embedding_semaphores",` with `"reset_embedding_limiters",`.

- [ ] **Step 3: Update `runtime_settings_apply.py`**

At `api/bigrag/services/runtime_settings_apply.py:10`, replace:

```python
from bigrag.services.embedding import reset_embedding_semaphores
```

with:

```python
from bigrag.services.embedding import reset_embedding_limiters
```

At `api/bigrag/services/runtime_settings_apply.py:77-78`, replace:

```python
        if "embedding_concurrency" in keyset:
            reset_embedding_semaphores()
```

with:

```python
        if "embedding_concurrency" in keyset:
            reset_embedding_limiters()
```

- [ ] **Step 4: Confirm no dangling references**

Run: `grep -rn "reset_embedding_semaphores\|get_semaphore" api/bigrag/services/embedding api/bigrag/services/runtime_settings_apply.py`
Expected: no output. (The only other `get_semaphore` is in `api/bigrag/services/webhook/`, unrelated and untouched.)

- [ ] **Step 5: Lint**

Run: `api/.venv/bin/ruff check api/bigrag/services/embedding/base.py api/bigrag/services/embedding/__init__.py api/bigrag/services/runtime_settings_apply.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add api/bigrag/services/embedding/base.py api/bigrag/services/embedding/__init__.py api/bigrag/services/runtime_settings_apply.py
git commit -m "refactor: drop per-process embedding semaphores"
```

---

### Task 4: Remove now-redundant cooldown logic from the ingestion path

The gate owns cooldown waiting and recording. Remove the duplicate handling and the vestigial `cooldown_key` threading.

**Files:**
- Modify: `api/bigrag/services/queue_embedding/embed.py:1-21,51-96`
- Modify: `api/bigrag/services/queue_embedding/embed_batches.py:1-19,22-30,80`
- Modify: `api/bigrag/services/queue_embedding/plan.py:9,19,63-68,135`
- Modify: `api/bigrag/services/queue_embedding/insert.py:31-38`

- [ ] **Step 1: Simplify `embed.py` imports/header**

Replace `api/bigrag/services/queue_embedding/embed.py:1-21`:

```python
from __future__ import annotations

import asyncio
import math
import time

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.embedding import truncate_to_tokens
from bigrag.services.embedding_rate_limit import (
    is_rate_limit_error,
    rate_limit_cooldown_key,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)

logger = get_logger("bigrag.queue")

EMBEDDING_TIMEOUT_SECONDS = 60
PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)
```

with:

```python
from __future__ import annotations

import math
import time

from bigrag.logging import get_logger
from bigrag.services import embedding_cache
from bigrag.services.embedding import truncate_to_tokens

logger = get_logger("bigrag.queue")

PERMANENT_ERRORS = (ValueError, UnicodeDecodeError, KeyError)
```

(`asyncio`, `EMBEDDING_TIMEOUT_SECONDS`, and all `embedding_rate_limit` imports become unused — the gate handles cooldowns and the per-call timeout already lives inside each provider's `_embed_single`.)

- [ ] **Step 2: Simplify the provider call in `embed.py`**

Replace `api/bigrag/services/queue_embedding/embed.py:51-96` (the `if missing_idx:` block through the function's final `return`):

```python
    if missing_idx:
        missing_by_cache_text: dict[str, int] = {}
        for idx in missing_idx:
            missing_by_cache_text.setdefault(cache_texts[idx], idx)
        provider_idx = list(missing_by_cache_text.values())
        missing_texts = [texts[i] for i in provider_idx]
        missing_cache_texts = [cache_texts[i] for i in provider_idx]
        cooldown_key = rate_limit_cooldown_key(model, provider, model_name, dimension)
        await wait_for_rate_limit_cooldown(cooldown_key, provider, model_name)
        t0 = time.monotonic()
        logger.debug(
            "embedding provider request",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
        )
        try:
            fresh = await asyncio.wait_for(
                model.embed(missing_texts, input_type=input_type),
                timeout=EMBEDDING_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            if is_rate_limit_error(exc):
                await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
            raise
        logger.debug(
            "embedding provider response",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
            elapsed=round(time.monotonic() - t0, 2),
        )
        if len(fresh) != len(missing_texts):
            raise ValueError(
                f"embedding provider returned {len(fresh)} vectors for {len(missing_texts)} inputs"
            )
        for vec in fresh:
            if any(not math.isfinite(v) for v in vec):
                raise ValueError("embedding provider returned non-finite values")
        await embedding_cache.put_many(
            missing_cache_texts, fresh, model.cache_identity, dimension, input_type
        )
        fresh_by_cache_text = dict(zip(missing_cache_texts, fresh, strict=False))
        for idx in missing_idx:
            cached[idx] = fresh_by_cache_text[cache_texts[idx]]
    return [cached[i] for i in range(len(texts))]
```

with:

```python
    if missing_idx:
        missing_by_cache_text: dict[str, int] = {}
        for idx in missing_idx:
            missing_by_cache_text.setdefault(cache_texts[idx], idx)
        provider_idx = list(missing_by_cache_text.values())
        missing_texts = [texts[i] for i in provider_idx]
        missing_cache_texts = [cache_texts[i] for i in provider_idx]
        t0 = time.monotonic()
        logger.debug(
            "embedding provider request",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
        )
        fresh = await model.embed(missing_texts, input_type=input_type)
        logger.debug(
            "embedding provider response",
            provider=provider,
            model=model_name,
            inputs=len(missing_texts),
            elapsed=round(time.monotonic() - t0, 2),
        )
        if len(fresh) != len(missing_texts):
            raise ValueError(
                f"embedding provider returned {len(fresh)} vectors for {len(missing_texts)} inputs"
            )
        for vec in fresh:
            if any(not math.isfinite(v) for v in vec):
                raise ValueError("embedding provider returned non-finite values")
        await embedding_cache.put_many(
            missing_cache_texts, fresh, model.cache_identity, dimension, input_type
        )
        fresh_by_cache_text = dict(zip(missing_cache_texts, fresh, strict=False))
        for idx in missing_idx:
            cached[idx] = fresh_by_cache_text[cache_texts[idx]]
    return [cached[i] for i in range(len(texts))]
```

- [ ] **Step 3: Trim `embed_batches.py` imports**

Replace `api/bigrag/services/queue_embedding/embed_batches.py:7-12`:

```python
from bigrag.services.embedding_rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    is_rate_limit_error,
    rate_limit_delay,
    record_rate_limit_cooldown,
)
```

with:

```python
from bigrag.services.embedding_rate_limit import (
    MAX_RATE_LIMIT_RETRIES,
    is_rate_limit_error,
    rate_limit_delay,
)
```

- [ ] **Step 4: Drop `cooldown_key` from `embed_all_batches` signature**

Replace `api/bigrag/services/queue_embedding/embed_batches.py:22-30`:

```python
async def embed_all_batches(
    job: IngestionJob,
    prefix: str,
    *,
    embedding_model,
    cooldown_key: str,
    batches: list[tuple[int, int, int, list]],
    total_batches: int,
) -> list[tuple[int, int, int, list, list[list[float]], float]]:
```

with:

```python
async def embed_all_batches(
    job: IngestionJob,
    prefix: str,
    *,
    embedding_model,
    batches: list[tuple[int, int, int, list]],
    total_batches: int,
) -> list[tuple[int, int, int, list, list[list[float]], float]]:
```

- [ ] **Step 5: Remove the redundant cooldown write in the retry loop**

In `api/bigrag/services/queue_embedding/embed_batches.py`, delete the single line (line 80):

```python
                    await record_rate_limit_cooldown(cooldown_key, delay)
```

Leave the `fallback_delay` / `delay` computation, the `logger.warning(...)`, and `await asyncio.sleep(delay)` exactly as they are — the retry/backoff loop remains the safety net; only the cooldown *write* is removed (the gate already recorded it).

- [ ] **Step 6: Drop `cooldown_key` from `plan.py`**

In `api/bigrag/services/queue_embedding/plan.py`:
- delete the import at line 9: `from bigrag.services.embedding_rate_limit import rate_limit_cooldown_key`;
- delete the `cooldown_key: str` field from the `EmbedPlan` dataclass (line 19);
- delete the cooldown_key computation block (lines 63-68):

```python
    cooldown_key = rate_limit_cooldown_key(
        embedding_model,
        job.embedding_provider,
        job.embedding_model,
        job.embedding_dimension,
    )
```

- delete the `cooldown_key=cooldown_key,` line inside the `EmbedPlan(...)` return (line 135).

- [ ] **Step 7: Drop `cooldown_key` from the `insert.py` call**

Replace `api/bigrag/services/queue_embedding/insert.py:31-38`:

```python
    embed_results = await embed_all_batches(
        job,
        prefix,
        embedding_model=plan.embedding_model,
        cooldown_key=plan.cooldown_key,
        batches=plan.batches,
        total_batches=plan.total_batches,
    )
```

with:

```python
    embed_results = await embed_all_batches(
        job,
        prefix,
        embedding_model=plan.embedding_model,
        batches=plan.batches,
        total_batches=plan.total_batches,
    )
```

- [ ] **Step 8: Lint the ingestion path**

Run: `api/.venv/bin/ruff check api/bigrag/services/queue_embedding/`
Expected: `All checks passed!` (verifies no unused imports / undefined names remain).

- [ ] **Step 9: Commit**

```bash
git add api/bigrag/services/queue_embedding/embed.py api/bigrag/services/queue_embedding/embed_batches.py api/bigrag/services/queue_embedding/plan.py api/bigrag/services/queue_embedding/insert.py
git commit -m "refactor: let the gate own embedding cooldowns"
```

---

### Task 5: Document the semantic change of `embedding_concurrency`

**Files:**
- Modify: `api/bigrag/services/runtime_setting_specs/search.py:12`

- [ ] **Step 1: Update the setting description**

In `api/bigrag/services/runtime_setting_specs/search.py`, replace line 12:

```python
        description="Maximum concurrent embedding requests per provider endpoint.",
```

with:

```python
        description="Global ceiling on concurrent embedding requests per endpoint across all workers; the limiter backs off below this on rate limits and recovers toward it.",
```

- [ ] **Step 2: Lint**

Run: `api/.venv/bin/ruff check api/bigrag/services/runtime_setting_specs/search.py`
Expected: `All checks passed!`

- [ ] **Step 3: Commit**

```bash
git add api/bigrag/services/runtime_setting_specs/search.py
git commit -m "docs: clarify embedding_concurrency is a global adaptive ceiling"
```

---

### Task 6: Full-package lint + manual verification

**Files:** none (verification only).

- [ ] **Step 1: Lint the whole touched surface**

Run: `api/.venv/bin/ruff check api/bigrag`
Expected: `All checks passed!`

- [ ] **Step 2: Format check**

Run: `api/.venv/bin/ruff format --check api/bigrag/services/embedding_gate.py api/bigrag/services/embedding api/bigrag/services/queue_embedding`
Expected: `N files already formatted`. If it lists files that would be reformatted, run `api/.venv/bin/ruff format <those files>`, review the diff, and amend the relevant commit.

- [ ] **Step 3: Manual load-test verification (requires a running stack + Redis)**

With the API + workers running against a local Redis, drive ingestion using the existing load test in `tests/load/` (see `tests/load/test.sh`). While it runs, watch the worker logs:

- Confirm `embedding limit decreased` warnings appear *when* a 429 occurs (the gate detects and backs off).
- Confirm the prior flood of `batch rate limited` / repeated 429 warnings drops sharply after the first backoff (the herd is tamed).
- Optionally inspect Redis: `redis-cli --scan --pattern 'bigrag:embedding:limit:*'`, then `GET <key>` — the live limit should settle below `embedding_concurrency` after 429s and recover toward it.

Tuning: if 429s remain frequent, lower `embedding_concurrency` (now global); if throughput is low and there are no 429s, raise it.

- [ ] **Step 4: Push the branch**

```bash
git push
```

---

## Notes for the implementer

- **No tests:** this repo has no unit-test framework (only `tests/load`). Verification is ruff + the load test, per project convention.
- **Lua numeric returns truncate to int** and the Redis client uses `decode_responses=False`, so `_SUCCESS_LUA` / `_DECREASE_LUA` `return tostring(limit)` and Python parses the resulting **bytes** via `_as_float` (`float(raw.decode())`). Do not change these to return numbers.
- **`register_script` not direct script execution:** scripts are registered once per client (`_script` helper, cached in `_scripts`) so the redis client uses EVALSHA under the hood. `_acquire` returns int `1`/`0` directly.
- **Fail-open is deliberate:** if a Redis script call raises, `_acquire` returns `_FAILOPEN_TOKEN` and admits the request rather than stalling ingestion. Release/success/decrease for that token are no-ops.
- **Permit leaks self-heal:** each permit is a ZSET member scored with its expiry; `_acquire` reaps expired members first, so a crashed worker frees its slots after `LEASE_SECONDS`.
- **Per-job `EMBED_CONCURRENCY` stays:** the local per-job fan-out bound in `embed_batches.py` is left intact; it is now subordinate to the global gate.
- **The webhook `get_semaphore`** (`api/bigrag/services/webhook/http.py`) is a different, unrelated function — do not touch it.
```
