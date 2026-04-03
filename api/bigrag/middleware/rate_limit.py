"""Simple in-memory rate limiter for auth endpoints."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """Sliding window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._requests[key] and self._requests[key][0] <= cutoff:
            self._requests[key].popleft()

    async def __call__(self, request: Request) -> None:
        ip = self._get_client_ip(request)
        now = time.monotonic()
        self._cleanup(ip, now)

        if len(self._requests[ip]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )

        self._requests[ip].append(now)


# 10 auth attempts per minute per IP
auth_rate_limit = RateLimiter(max_requests=10, window_seconds=60)
