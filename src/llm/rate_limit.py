import threading
import time


class RateLimiter:
    """Token-bucket rate limiter with a per-minute capacity.

    Thread-safe: `wait` blocks the calling thread until a token is available.
    """

    def __init__(self, max_per_minute: int = 60):
        self._max_per_minute = max_per_minute
        self._tokens = float(max_per_minute)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until a token is available, or return immediately if disabled."""
        if self._max_per_minute <= 0:
            return
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                seconds_per_token = 60.0 / self._max_per_minute
                delay = max(0.0, (1.0 - self._tokens) * seconds_per_token)
            time.sleep(delay)

    def _refill(self) -> None:
        """Replenish tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._max_per_minute,
            self._tokens + elapsed * self._max_per_minute / 60.0,
        )
        self._last_refill = now
