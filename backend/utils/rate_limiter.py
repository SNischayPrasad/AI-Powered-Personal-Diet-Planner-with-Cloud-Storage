"""In-memory sliding-window rate limiter.

Protects login/registration from brute-force attempts and the plan generator (which may call
a paid AI API) from abuse. A request is allowed if fewer than ``limit`` requests from the same
key (client IP or user) happened in the last ``window_seconds``.

Cloud note: this state lives in one server's memory. With several instances behind a load
balancer each instance counts separately — production systems move the counters to a shared
store (Redis / ElastiCache) or enforce limits at the API gateway (AWS API Gateway throttling,
Cloudflare, Vercel Firewall).
"""

import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from backend.utils.errors import RateLimitExceededError


class SlidingWindowRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> float | None:
        """Record a request. Returns ``None`` if allowed, otherwise the seconds to wait."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return max(0.0, hits[0] + window_seconds - now)
            hits.append(now)
            return None


def client_ip(request: Request) -> str:
    """The caller's IP. Behind a trusted proxy/CDN use the first X-Forwarded-For entry;
    otherwise ignore that header, because clients could forge it to dodge rate limits."""
    if request.app.state.settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded.strip():
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, key: str, limit: int, window_seconds: float = 60) -> None:
    retry_after = request.app.state.rate_limiter.hit(key, limit, window_seconds)
    if retry_after is not None:
        raise RateLimitExceededError(headers={"Retry-After": str(max(1, math.ceil(retry_after)))})


def auth_rate_limit(request: Request) -> None:
    """Dependency for /register and /login: limit attempts per client IP."""
    enforce_rate_limit(
        request,
        key=f"auth:{client_ip(request)}",
        limit=request.app.state.settings.rate_limit_auth_per_minute,
    )
