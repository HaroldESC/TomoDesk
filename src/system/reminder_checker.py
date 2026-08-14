import logging
import threading
from typing import Dict

from src.memory.memory import MemoryManager

logger = logging.getLogger(__name__)


class ReminderChecker:
    def __init__(
        self,
        memory_manager: MemoryManager,
        config: Dict,
        check_interval: float = 30.0,
    ):
        self.memory_manager = memory_manager
        self.config = config
        self.check_interval = check_interval
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_reminder_callback = None

    def set_callback(self, callback):
        self._on_reminder_callback = callback

    def start(self):
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("ReminderChecker started")

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
        logger.info("ReminderChecker stopped")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                due_reminders = self.memory_manager.get_due_reminders()
                for reminder in due_reminders:
                    logger.info(
                        "Reminder #%d due: %s", reminder["id"], reminder["message"]
                    )
                    try:
                        if self._on_reminder_callback:
                            self._on_reminder_callback(reminder["message"])
                    except Exception as e:
                        logger.error("Reminder callback failed for #%d: %s", reminder["id"], e)
                        continue
                    self.memory_manager.deactivate_reminder(reminder["id"])
                    self.memory_manager.log_interaction(
                        "reminder_triggered",
                        {
                            "reminder_id": reminder["id"],
                            "message": reminder["message"],
                        },
                    )
            except Exception as e:
                logger.error("Error checking reminders: %s", e)

            self._stop_event.wait(self.check_interval)

    @property
    def is_running(self) -> bool:
        return self._running
