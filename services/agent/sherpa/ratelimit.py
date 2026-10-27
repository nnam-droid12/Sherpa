"""Per-client rate limiting so a public demo can't burn browser and model credits."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from sherpa.config import get_settings


class RateLimiter:
    def __init__(self, limit: int, window_s: int = 3600) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            wait = int(self.window_s - (now - hits[0])) // 60 + 1
            raise HTTPException(
                429,
                f"Demo limit reached ({self.limit} runs per hour). Try again in about {wait} minutes, "
                "or open a recent run from the demo store cards.",
            )
        hits.append(now)


_limiter: RateLimiter | None = None


def client_key(request: Request) -> str:
    # The console forwards the browser's IP; fall back to the direct peer.
    return request.headers.get("x-client-ip") or (request.client.host if request.client else "unknown")


def enforce(request: Request) -> None:
    global _limiter
    s = get_settings()
    if not s.demo_mode:
        return
    if _limiter is None:
        _limiter = RateLimiter(s.runs_per_hour)
    _limiter.check(client_key(request))
