# Adaptive Embedding Rate Limiting

**Date:** 2026-05-24
**Status:** Design — pending review

## Problem

Production logs show frequent embedding `429` hits. Repeatedly hammering a
provider after `429`s risks an abuse ban, so the goal is to **minimize how often
we hit the limit**, not just survive it.

The current handling is purely reactive and uncoordinated:

1. **No proactive pacing.** Requests fire at full speed until a `429` returns.
   Only then does `record_rate_limit_cooldown` write a Redis cooldown
   (`embed.py:74`, `openai.py:109`, `cohere.py:86`, `voyage.py:117/132`). Steady
   state is a sawtooth: blast → `429` → everyone waits `Retry-After` → cooldown
   expires → everyone blasts again in lockstep → immediate re-`429`.

2. **Concurrency limits are per-process.** `EMBED_CONCURRENCY = 8`
   (`embed_batches.py:19`, a fresh semaphore per job) and `get_semaphore`
   (`base.py:30`, default 8) live in process-local memory bound to each thread's
   event loop. With **5 worker processes × 8 threads**, true in-flight
   concurrency to the provider is dozens, not 8. The `embedding_concurrency`
   runtime setting is effectively meaningless at this scale.

3. **TPM is never modeled.** OpenAI embeddings are gated mainly by
   tokens-per-minute. A batch can be 512 chunks → up to 2048 inputs/request.
   Nothing counts tokens, so even modest concurrency trips TPM.

## Constraints (from brainstorming)

- **Must work for all providers** (OpenAI, Cohere, Voyage, OpenAI-compatible).
  Testing with OpenAI first.
- **No hardcoded or fetched RPM/TPM limits.** Configuring or fetching quotas is
  considered brittle and wasteful. The only source of truth for "how fast can we
  go" is the `429` signal itself.
- Keep the existing `Retry-After` cooldown behavior ("wait the time, continue").
- Must coordinate across the **5 workers** that share one API key.

## Approach: self-tuning adaptive concurrency (AIMD)

Because we refuse to configure or fetch the limit, the safe rate must be
**learned from feedback**. We use AIMD (additive-increase / multiplicative
decrease, the TCP congestion-control pattern): a shared, dynamically-sized
concurrency limit per endpoint, stored in Redis so all 5 workers obey the same
ceiling.

- **On success:** nudge the allowed concurrency up.
- **On `429`:** cut it multiplicatively *and* set the existing `Retry-After`
  cooldown.

This replaces the fixed per-process semaphores with one cross-worker limiter.
**No token counting is needed:** large (high-token) requests trip `429`s sooner,
which lowers concurrency automatically — so AIMD adapts to TPM pressure
implicitly. The net behavior changes from `blast → 429 → wait → blast → 429`
to `ramp up → find the edge → one 429 → back off → settle just under the edge`.

## Architecture

### New module: `services/embedding_gate.py`

A single async context manager that every provider call site uses. It absorbs
the duplicated `get_semaphore` + `wait_for_rate_limit_cooldown` +
`record_rate_limit_cooldown` logic currently copy-pasted across the three
providers.

```python
@asynccontextmanager
async def embedding_gate(endpoint_key: str, provider: str, model_name: str):
    await wait_for_rate_limit_cooldown(cooldown_key, provider, model_name)  # existing
    token = await _acquire(endpoint_key)          # block until an adaptive slot frees
    try:
        yield                                     # caller runs the HTTP request here
    except Exception as exc:
        if is_rate_limit_error(exc):
            await _on_rate_limited(endpoint_key, exc)   # AIMD decrease + record cooldown
        raise
    else:
        await _on_success(endpoint_key)           # AIMD increase
    finally:
        await _release(endpoint_key, token)       # always free the slot
```

`endpoint_key` is derived from `cache_identity` (already
`provider:model:dimension[:base_tag]`), so each distinct provider/model/endpoint
gets its own independent limiter — matching the existing cooldown key.

### Redis state (per endpoint)

| Key | Type | Purpose |
|-----|------|---------|
| `bigrag:embedding:inflight:{hash}` | ZSET | in-flight permits; member = unique token, score = lease expiry (ms) |
| `bigrag:embedding:limit:{hash}` | string (float) | current AIMD concurrency limit |
| `bigrag:embedding:limit-dec:{hash}` | string (ms) | timestamp of last decrease (decrease guard) |
| `bigrag:embedding:rate-limit:{hash}` | string | **existing** `Retry-After` cooldown (unchanged) |

The ZSET doubles as a **self-healing lease**: each acquire reaps members whose
score (expiry) is in the past, so a crashed worker's permits free themselves
after the request timeout (`EMBEDDING_TIMEOUT_SECONDS = 60`). This prevents
permanent permit leaks / deadlock.

### Atomic operations (Lua via `redis.eval`)

**Acquire** — reap expired permits, init limit if missing, admit only if under
limit:

```lua
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])   -- reap (now)
local limit = tonumber(redis.call('GET', KEYS[2]))
if limit == nil then limit = tonumber(ARGV[4]); redis.call('SET', KEYS[2], limit) end
local count = redis.call('ZCARD', KEYS[1])
if count < math.floor(limit) then
  redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])            -- score = lease expiry
  redis.call('PEXPIRE', KEYS[1], ARGV[5])
  return 1
end
return 0
```

Caller loop: if `0`, sleep a short jittered interval (e.g. 25–100 ms) and retry.
This is the proactive throttle — workers wait *before* sending instead of after
a `429`.

**On success** — release token, additive increase (TCP-style: `+1/limit` per
success, so it takes ~`limit` successes to add one slot):

```lua
redis.call('ZREM', KEYS[1], ARGV[3])
local limit = tonumber(redis.call('GET', KEYS[2])) or tonumber(ARGV[4])
limit = math.min(limit + 1.0/limit, tonumber(ARGV[5]))     -- cap at MAX
redis.call('SET', KEYS[2], limit)
```

**On `429`** — release token, multiplicative decrease with a guard so a burst of
simultaneous `429`s applies **one** halving, not many:

```lua
redis.call('ZREM', KEYS[1], ARGV[3])
local last = tonumber(redis.call('GET', KEYS[3])) or 0
if tonumber(ARGV[1]) - last > tonumber(ARGV[6]) then       -- guard window
  local limit = tonumber(redis.call('GET', KEYS[2])) or tonumber(ARGV[4])
  limit = math.max(limit * 0.5, tonumber(ARGV[7]))         -- floor at MIN
  redis.call('SET', KEYS[2], limit)
  redis.call('SET', KEYS[3], ARGV[1])
end
```

The existing `record_rate_limit_cooldown` is still called on `429` so all workers
also pause for the provider's `Retry-After`.

### Constants (safety bounds, not provider limits)

These bound the *learning*, not the provider quota — AIMD settles below the true
limit regardless.

- `MIN_LIMIT = 1`
- `MAX_LIMIT = 64` (growth ceiling; prevents runaway under a generous quota)
- `INITIAL_LIMIT = 8` (matches today's default so day-one behavior is familiar)
- `DECREASE_GUARD_MS = 1000` (one halving per burst)
- `ACQUIRE_RETRY_MS = 25–100` jittered
- lease = `EMBEDDING_TIMEOUT_SECONDS` (60s)

### Local fallback (no Redis)

Mirror the cooldown module's existing pattern: a process-local
`{endpoint_key: AdaptiveLimiter}` using an `asyncio` counter + condition variable
with the same AIMD math. Keeps single-process/dev working. (The 5-worker
coordination benefit only applies with Redis, which production has.)

## Call-site changes

Replace the duplicated block in each provider's `_embed_single` with the gate:

- `services/embedding/openai.py:93` — `OpenAIEmbedding._embed_single`
- `services/embedding/cohere.py:68` — `CohereEmbedding._embed_single`
- `services/embedding/voyage.py:92` — `VoyageEmbedding._embed_single`

Before:
```python
async with await get_semaphore(self._semaphore_key):
    await wait_for_rate_limit_cooldown(cooldown_key, ...)
    try:
        response = await asyncio.wait_for(call(...), timeout=60)
    except Exception as exc:
        if is_rate_limit_error(exc):
            await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
        raise
```

After:
```python
async with embedding_gate(self._cache_identity, self.provider, self._model_name):
    response = await asyncio.wait_for(call(...), timeout=60)
```

`get_semaphore` / `reset_embedding_semaphores` in `base.py` become unused and are
removed. `embed.py:embed_with_cache` wraps `model.embed`, which fans out to
`_embed_single` where the gate now lives — so its pre-call
`wait_for_rate_limit_cooldown` and its on-`429` `record_rate_limit_cooldown`
(`embed.py:59,74`) are removed to keep the gate the single point of admission and
avoid double-handling. The per-job `EMBED_CONCURRENCY` semaphore in
`embed_batches.py` stays as a local per-job fan-out bound but is now subordinate
to the global gate.

Query-time embedding (`retrieval/cache.py:90,127`) calls `model.embed` →
`_embed_single`, so it inherits the gate automatically. No change there.

## Observability

Structured logs (existing `get_logger` style) when the limit changes:
`embedding limit decreased` / `embedding limit recovered`, with `endpoint`,
`old_limit`, `new_limit`, `inflight`. This makes "are we still hitting 429s"
directly visible and shows the limit settling at the discovered ceiling.

## Error handling

- **Redis unavailable:** fall back to the local adaptive limiter; never block
  embedding on Redis errors. Wrap Lua calls; on exception, log and admit (fail
  open) so a Redis blip can't stall ingestion.
- **Permit leak on crash:** healed by the lease TTL reap in `_acquire`.
- **Burst of concurrent 429s:** collapsed to a single halving by the decrease
  guard, so `limit` can't crater to 1 from one bad moment.
- **`MAX_RATE_LIMIT_RETRIES` / backoff in `embed_batches.py`:** unchanged; still
  the safety net if the learned limit lags a sudden quota cut.

## Testing

- **AIMD math:** unit tests for increase (`+1/limit`), decrease (`*0.5` floored),
  and the decrease guard (N concurrent 429s → one halving).
- **Lua acquire/release:** against a real/fake Redis — admission under limit,
  rejection at limit, expired-lease reaping.
- **Concurrency simulation:** many coroutines through the gate never exceed
  `floor(limit)` in flight.
- **429 adaptation:** simulate provider 429s; assert limit halves, cooldown is
  recorded, then recovers on sustained success.
- **Local fallback:** same behaviors with Redis disabled.
- **Provider integration:** each provider's `_embed_single` admits/blocks via the
  gate (mock the HTTP client).

## Out of scope

- Configuring or fetching provider RPM/TPM (explicitly rejected).
- Token-budget accounting (handled implicitly by AIMD).
- Changing batch sizes or the Dramatiq worker topology.
```
