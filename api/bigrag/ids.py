from __future__ import annotations

import secrets
import threading
import time
import uuid

_MASK_12 = (1 << 12) - 1
_MASK_48 = (1 << 48) - 1
_MASK_62 = (1 << 62) - 1
_UUID7_LOCK = threading.Lock()
_LAST_UUID7_INT = 0


def _uuid7_int(unix_ms: int, rand_a: int, rand_b: int) -> int:
    return (
        ((unix_ms & _MASK_48) << 80)
        | (7 << 76)
        | ((rand_a & _MASK_12) << 64)
        | (2 << 62)
        | (rand_b & _MASK_62)
    )


def _next_uuid7_int(value: int) -> int:
    unix_ms = value >> 80
    rand_a = (value >> 64) & _MASK_12
    rand_b = value & _MASK_62
    if rand_b < _MASK_62:
        rand_b += 1
    elif rand_a < _MASK_12:
        rand_a += 1
        rand_b = 0
    else:
        unix_ms = (unix_ms + 1) & _MASK_48
        rand_a = 0
        rand_b = 0
    return _uuid7_int(unix_ms, rand_a, rand_b)


def uuid7() -> uuid.UUID:
    global _LAST_UUID7_INT

    now_ns = time.time_ns()
    unix_ms = now_ns // 1_000_000
    sub_ms = ((now_ns % 1_000_000) << 12) // 1_000_000
    candidate = _uuid7_int(unix_ms, sub_ms, secrets.randbits(62))
    with _UUID7_LOCK:
        if candidate <= _LAST_UUID7_INT:
            candidate = _next_uuid7_int(_LAST_UUID7_INT)
        _LAST_UUID7_INT = candidate
    return uuid.UUID(int=candidate)
