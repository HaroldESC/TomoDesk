import logging
import random
import threading
import time
from typing import Dict

logger = logging.getLogger(__name__)


class ProactivePolicy:
    def __init__(self, config: Dict):
        self.config = config
        self._last_comment_time: float = 0.0
        self._comment_timestamps: list = []
        self._lock = threading.Lock()
        self._focus_mode = False
        self._dnd_mode = False

    @property
    def comments_enabled(self) -> bool:
        return self.config.get("modes", {}).get("proactive_comments", False)

    @property
    def cooldown_seconds(self) -> int:
        return self.config.get("modes", {}).get("proactive_cooldown_seconds", 1800)

    @property
    def max_per_hour(self) -> int:
        return self.config.get("modes", {}).get("max_comments_per_hour", 2)

    @property
    def random_probability(self) -> float:
        return self.config.get("modes", {}).get("comment_probability", 0.1)

    def set_focus_mode(self, enabled: bool) -> None:
        self._focus_mode = enabled
        logger.info("Focus mode: %s", "ON" if enabled else "OFF")

    def set_dnd_mode(self, enabled: bool) -> None:
        self._dnd_mode = enabled
        logger.info("Do Not Disturb mode: %s", "ON" if enabled else "OFF")

    def is_enabled(self) -> bool:
        return self.comments_enabled and not self._focus_mode and not self._dnd_mode

    def can_comment(self, trigger_type: str) -> bool:
        with self._lock:
            if trigger_type == "session_start":
                return True

            if not self.comments_enabled:
                return False

            if self._focus_mode or self._dnd_mode:
                return False

            elapsed = time.time() - self._last_comment_time
            if elapsed < self.cooldown_seconds:
                logger.debug(
                    "Cooldown active: %.0fs < %ds", elapsed, self.cooldown_seconds
                )
                return False

            self._clean_old_timestamps()
            if len(self._comment_timestamps) >= self.max_per_hour:
                logger.debug(
                    "Hourly limit: %d >= %d",
                    len(self._comment_timestamps),
                    self.max_per_hour,
                )
                return False

            if trigger_type == "random":
                if random.random() > self.random_probability:
                    return False

            return True

    def record_comment(self) -> None:
        with self._lock:
            now = time.time()
            self._last_comment_time = now
            self._comment_timestamps.append(now)

    def _clean_old_timestamps(self) -> None:
        cutoff = time.time() - 3600
        self._comment_timestamps = [t for t in self._comment_timestamps if t > cutoff]

    def get_stats(self) -> Dict:
        with self._lock:
            self._clean_old_timestamps()
            return {
                "enabled": self.comments_enabled,
                "focus_mode": self._focus_mode,
                "dnd_mode": self._dnd_mode,
                "comments_this_hour": len(self._comment_timestamps),
                "seconds_since_last": (
                    time.time() - self._last_comment_time
                    if self._last_comment_time > 0
                    else None
                ),
                "cooldown_remaining": (
                    max(
                        0,
                        self.cooldown_seconds
                        - (time.time() - self._last_comment_time),
                    )
                    if self._last_comment_time > 0
                    else 0
                ),
            }
