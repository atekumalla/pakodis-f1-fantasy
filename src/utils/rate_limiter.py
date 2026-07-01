"""Rate limiter — prevents excessive API calls."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple per-function rate limiter with configurable cooldown."""

    def __init__(self, cooldown_seconds: int = 600):
        self.cooldown_seconds = cooldown_seconds
        self._last_called: dict[str, float] = {}

    def can_call(self, key: str) -> bool:
        last = self._last_called.get(key, 0)
        return (time.time() - last) >= self.cooldown_seconds

    def seconds_until_ready(self, key: str) -> int:
        last = self._last_called.get(key, 0)
        elapsed = time.time() - last
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))

    def record_call(self, key: str):
        self._last_called[key] = time.time()

    def try_call(self, key: str) -> tuple[bool, int]:
        if self.can_call(key):
            self.record_call(key)
            return True, 0
        else:
            remaining = self.seconds_until_ready(key)
            logger.warning(
                f"Rate limited: '{key}' called too soon. "
                f"Wait {remaining}s (cooldown: {self.cooldown_seconds}s)"
            )
            return False, remaining

    def reset(self, key: str):
        self._last_called.pop(key, None)


rate_limiter = RateLimiter(cooldown_seconds=600)
