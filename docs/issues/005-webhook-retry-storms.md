# 005: Webhook Retry Storms

**Status:** Open
**Severity:** Medium
**Component:** `api/bigrag/services/webhook.py`

## Problem

When a webhook endpoint goes down, all deliveries to it retry on the same fixed schedule with no adaptive backoff, no per-webhook circuit breaker, and no concurrency limit. If the endpoint recovers after extended downtime, all pending retries fire simultaneously, potentially overwhelming it again.

## Current Delivery Lifecycle

```
Event published (queue.py:305-314)
    ↓
WebhookDispatcher._listen() receives event (webhook.py:114-127)
    ↓
_handle_event() matches webhooks (webhook.py:129-150)
    ↓
safe_create_task(_deliver()) — fire-and-forget asyncio task (webhook.py:147)
    ↓
_deliver() runs retry loop:
    Attempt 1: POST immediately (10s HTTP timeout)
    Attempt 2: sleep(10s), POST
    Attempt 3: sleep(30s), POST
    Attempt 4: sleep(90s), POST
    Mark 'failed' if all 4 fail
    ↓
Task completes (130s total lifetime for failed delivery)
```

**Config:** `webhook.py` uses `config.py:42-44`:
- `webhook_delivery_timeout: int = 10` (HTTP request timeout)
- `webhook_retry_delays: list[int] = [10, 30, 90]` (sleep between retries)
- `webhook_cache_ttl: int = 60`

## Quantified Impact

### Scenario: Webhook down for 1 hour, 10 docs/minute

| Metric | Value |
|--------|-------|
| Documents processed | 600 |
| Delivery tasks created | 600 |
| HTTP attempts (4 per delivery) | 2,400 |
| Total retry delay per delivery | 130s |
| Steady-state concurrent tasks | ~22 |
| Peak concurrent tasks | ~22 |
| DB operations (1 INSERT + 4 UPDATEs per delivery) | 3,000 |
| Total HTTP timeout wait (10s each) | 6.7 hours (spread across 22 concurrent tasks) |
| Wall-clock overhead | ~18 minutes |
| Memory impact | ~100 KB (negligible) |

**The memory impact is small.** The real costs are:
1. **Database churn:** 3,000 write operations for deliveries that will all fail
2. **Thundering herd on recovery:** When endpoint recovers, queued retry sleeps wake up in waves
3. **HTTP client pool exhaustion:** 22 concurrent HTTP requests to a single slow endpoint

### Scenario: 10 webhooks, all down, 10 docs/minute

Multiply by 10: 6,000 tasks, 24,000 HTTP attempts, 30,000 DB operations per hour. httpx connection pool (shared) may struggle.

## Issues

### 1. No per-webhook circuit breaker

Every matching event creates a new delivery attempt regardless of how many previous deliveries to that webhook have failed. A consistently broken webhook generates the same volume of failed deliveries as a healthy one processes successful ones.

**Lines:** `webhook.py:144-150` — no failure history check before creating task.

### 2. Fixed retry delays (no jitter)

All deliveries to the same webhook retry on exactly the same schedule: 10s, 30s, 90s. When a webhook URL recovers, all waiting retries for that URL wake up at similar times, creating a burst.

**Lines:** `webhook.py:249-265` — `retry_delays[retry_index]` is deterministic.

### 3. No concurrency limit per webhook

`safe_create_task()` creates unbounded asyncio tasks. All share one `httpx.AsyncClient`. No semaphore or rate limiter per webhook URL.

**Lines:** `webhook.py:147`, `utils.py:9-21` — task created with no limit check.

### 4. No task tracking

Created tasks are not stored or tracked. No way to:
- Count active delivery tasks
- Cancel all deliveries for a webhook
- Monitor delivery backlog

**Lines:** `utils.py:9-21` — `safe_create_task` returns the task but it's not saved.

### 5. Deliveries created before validation

The delivery record is inserted with `status='pending'` (line 187-196) before attempting the HTTP POST. If the `_deliver` coroutine crashes unexpectedly (not a retry failure), the record stays 'pending' forever.

## Proposed Fix

### Phase 1: Circuit breaker (recommended)

Track consecutive failures per webhook. After N consecutive failures, "open" the circuit — skip new deliveries for a cooldown period:

```python
class WebhookCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown: int = 300):
        self._failures: dict[str, int] = {}       # webhook_id → consecutive failures
        self._open_until: dict[str, float] = {}    # webhook_id → monotonic time
        self._threshold = failure_threshold
        self._cooldown = cooldown

    def is_open(self, webhook_id: str) -> bool:
        """Return True if circuit is open (webhook should be skipped)."""
        until = self._open_until.get(webhook_id)
        if until and time.monotonic() < until:
            return True
        if until and time.monotonic() >= until:
            # Cooldown expired, allow a probe request
            self._open_until.pop(webhook_id, None)
        return False

    def record_success(self, webhook_id: str) -> None:
        self._failures.pop(webhook_id, None)
        self._open_until.pop(webhook_id, None)

    def record_failure(self, webhook_id: str) -> None:
        count = self._failures.get(webhook_id, 0) + 1
        self._failures[webhook_id] = count
        if count >= self._threshold:
            self._open_until[webhook_id] = time.monotonic() + self._cooldown
            logger.warning(
                f"Circuit opened for webhook {webhook_id}: "
                f"{count} consecutive failures, cooldown {self._cooldown}s"
            )
```

Use in `_handle_event`:

```python
async def _handle_event(self, event):
    ...
    for webhook in webhooks:
        if _matches_webhook(webhook, webhook_event, collection):
            wh_id = str(webhook["id"])
            if self._circuit_breaker.is_open(wh_id):
                logger.debug(f"Skipping webhook {wh_id}: circuit open")
                continue
            safe_create_task(
                self._deliver(webhook, webhook_event, payload),
                name=f"webhook-deliver-{wh_id}",
            )
```

Update `_deliver` to report success/failure:

```python
# After successful delivery
self._circuit_breaker.record_success(str(webhook["id"]))

# After all retries exhausted
self._circuit_breaker.record_failure(str(webhook["id"]))
```

### Phase 2: Jitter on retry delays

Add randomized jitter to prevent thundering herd:

```python
import random

def _jittered_delay(base_delay: int) -> float:
    """Add +/-25% jitter to a delay."""
    jitter = base_delay * 0.25
    return base_delay + random.uniform(-jitter, jitter)
```

Use in `_deliver`:

```python
if retry_index < len(retry_delays):
    delay = _jittered_delay(retry_delays[retry_index])
    await asyncio.sleep(delay)
```

### Phase 3: Per-webhook concurrency limit

Add a semaphore per webhook to limit concurrent deliveries:

```python
class WebhookDispatcher:
    def __init__(self):
        ...
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, webhook_id: str) -> asyncio.Semaphore:
        if webhook_id not in self._semaphores:
            self._semaphores[webhook_id] = asyncio.Semaphore(5)  # max 5 concurrent
        return self._semaphores[webhook_id]

    async def _deliver(self, webhook, event, payload):
        wh_id = str(webhook["id"])
        async with self._get_semaphore(wh_id):
            # ... existing delivery logic ...
```

This limits concurrency to 5 deliveries per webhook URL, preventing a slow endpoint from consuming all HTTP connections.

### Phase 4: Auto-disable after sustained failure (optional)

After the circuit breaker opens N times (e.g., 3 consecutive cooldown cycles with no success), automatically set `webhooks.active = false` and log a warning:

```python
def record_failure(self, webhook_id: str) -> None:
    ...
    if self._open_count.get(webhook_id, 0) >= 3:
        logger.error(
            f"Auto-disabling webhook {webhook_id}: "
            f"circuit opened {self._open_count[webhook_id]} times"
        )
        # Update database: SET active = false
        safe_create_task(self._auto_disable(webhook_id))
```

This prevents a permanently broken webhook from generating endless failed deliveries.

## Configuration

Add to `config.py`:

```python
# Webhook circuit breaker
webhook_circuit_failure_threshold: int = 5
webhook_circuit_cooldown: int = 300  # seconds
webhook_max_concurrent_per_hook: int = 5
```

## Files to Modify

- `api/bigrag/services/webhook.py` — add circuit breaker, jitter, per-webhook semaphore
- `api/bigrag/config.py` — add circuit breaker and concurrency settings

## Testing

- Configure a webhook pointing to a down endpoint
- Process 100 documents, verify circuit opens after 5 failures
- Verify no new delivery tasks created during cooldown
- After cooldown, verify probe request is sent
- If probe succeeds, verify circuit closes and deliveries resume
- Load test: 10 webhooks, 5 down — verify healthy webhooks unaffected
- Verify jittered retry delays are not synchronized across deliveries
