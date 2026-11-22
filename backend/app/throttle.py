"""Tiny in-memory limiter for failed logins (single server; resets on restart)."""
from __future__ import annotations

import time
from collections import defaultdict, deque


class FailureThrottle:
    def __init__(self, window_seconds: int = 300, max_failures: int = 10):
        self._window = window_seconds
        self._max = max_failures
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        attempts = self._failures[key]
        cutoff = time.monotonic() - self._window
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        return len(attempts) >= self._max

    def record_failure(self, key: str) -> None:
        self._failures[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


agent_logins = FailureThrottle()
customer_logins = FailureThrottle()
