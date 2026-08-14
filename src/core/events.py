import ctypes
import logging
import threading
import time
from ctypes import wintypes
from datetime import datetime
from threading import Lock
from typing import Dict, List, Tuple

import psutil

logger = logging.getLogger(__name__)

try:
    import pygetwindow as gw
except ImportError:
    gw = None
    logger.warning("pygetwindow not available. Window detection disabled.")


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


_idle_warning_logged = False


def _get_idle_time_ms() -> int:
    global _idle_warning_logged
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return ctypes.windll.kernel32.GetTickCount() - lii.dwTime
    except Exception:
        if not _idle_warning_logged:
            logger.warning("Failed to get idle time, falling back to 0")
            _idle_warning_logged = True
    return 0


class SystemMonitor:
    def __init__(self, config=None):
        self._config = config
        psutil.cpu_percent(interval=None)

    def poll(self) -> Dict:
        enabled = True
        if self._config:
            enabled = bool(self._config.get("privacy", {}).get("monitor_active_window", True))
        try:
            win = gw.getActiveWindow()
            active_window = win.title if win else "Unknown"
        except Exception:
            active_window = "Unknown"
        if not enabled:
            active_window = "Unknown"

        idle_ms = _get_idle_time_ms()

        return {
            "timestamp": datetime.now().isoformat(),
            "active_window": active_window,
            "idle_time_seconds": idle_ms // 1000,
            "cpu_percent": round(psutil.cpu_percent(interval=0), 1),
            "ram_percent": round(psutil.virtual_memory().percent, 1),
        }


class EventMonitor:
    def __init__(self, memory_manager, config: Dict, poll_interval: float = 2.0):
        self._memory_manager = memory_manager
        self._config = config
        self._poll_interval = poll_interval
        self._system_monitor = SystemMonitor(self._config)
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_snapshot: Dict | None = None
        self._lock = Lock()
        self._last_window = None
        self._last_activity_time = time.time()
        self._session_start_time = time.time()
        self._window_open_times: Dict[str, float] = {}
        self._window_close_times: Dict[str, float] = {}
        self._app_switch_count = 0
        self._app_switch_window_start = time.time()
        self._first_app_today: set = set()
        self._trigger_callback = None
        self._state_manager = None

        self._event_buffer: List[Tuple[str, Dict | None]] = []
        self._buffer_lock = Lock()
        self._flush_interval = 30.0
        self._max_buffer_size = 50
        self._flush_thread: threading.Thread | None = None

    def set_state_manager(self, state_manager):
        self._state_manager = state_manager

    def set_trigger_callback(self, callback):
        self._trigger_callback = callback

    def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("EventMonitor started")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                snapshot = self._system_monitor.poll()
                with self._lock:
                    self._latest_snapshot = snapshot
                with self._buffer_lock:
                    self._event_buffer.append(("system_event", snapshot))
                    if len(self._event_buffer) >= self._max_buffer_size:
                        self._flush_events()
                self._check_triggers(snapshot)
            except Exception:
                logger.warning("Error during event polling", exc_info=True)
            self._stop_event.wait(self._poll_interval)

    def _check_triggers(self, snapshot: Dict) -> None:
        if self._trigger_callback is None:
            return

        current_window = snapshot["active_window"]
        idle_seconds = snapshot["idle_time_seconds"]
        current_time = time.time()

        # --- App opened (window changed to something new) ---
        if current_window != self._last_window and current_window != "Unknown":
            if self._state_manager:
                self._state_manager.update("window_change")
            if self._last_window is not None:
                if current_window not in self._window_open_times:
                    self._window_open_times[current_window] = current_time
                    if self._state_manager:
                        self._state_manager.update("new_app", intensity=0.8)
                    self._trigger_callback("app_opened", {"window": current_window})

                if self._last_window in self._window_open_times:
                    duration = current_time - self._window_open_times[self._last_window]
                    if duration > 1800:
                        self._trigger_callback(
                            "app_closed_after_long",
                            {
                                "window": self._last_window,
                                "duration_minutes": int(duration / 60),
                            },
                        )

                self._app_switch_count += 1
                if current_time - self._app_switch_window_start > 10:
                    if self._app_switch_count >= 5:
                        self._trigger_callback(
                            "app_switching_frequent",
                            {"count": self._app_switch_count},
                        )
                    self._app_switch_count = 0
                    self._app_switch_window_start = current_time
            else:
                self._window_open_times[current_window] = current_time
                if self._state_manager:
                    self._state_manager.update("new_app", intensity=0.8)
                self._trigger_callback("app_opened", {"window": current_window})

        # --- First app of day ---
        if current_window != "Unknown" and current_window not in self._first_app_today:
            self._first_app_today.add(current_window)
            if len(self._first_app_today) <= 5:
                self._trigger_callback("first_app_of_day", {"window": current_window})

        # --- Idle thresholds ---
        if idle_seconds > 600 and self._last_activity_time is not None:
            if self._state_manager:
                self._state_manager.update("idle", intensity=min(1.0, idle_seconds / 3600))
            self._trigger_callback("idle_long", {"idle_minutes": int(idle_seconds / 60)})
            self._last_activity_time = None

        if idle_seconds < 5 and self._last_activity_time is None:
            if self._state_manager:
                self._state_manager.update("return_from_idle")
            self._trigger_callback("session_return", {"idle_minutes": 0})
            self._last_activity_time = current_time

        if idle_seconds < 5:
            self._last_activity_time = current_time

        # --- App-specific detection ---
        window_lower = current_window.lower()
        if any(
            term in window_lower
            for term in ["spotify", "music", "youtube music"]
        ):
            self._trigger_callback("music_detected", {"window": current_window})

        if any(
            term in window_lower
            for term in [
                "visual studio",
                "code",
                "vim",
                "neovim",
                "intellij",
                "pycharm",
                "terminal",
                "cmd",
            ]
        ):
            self._trigger_callback("coding_detected", {"window": current_window})

        # --- Late night ---
        hour = datetime.now().hour
        if hour >= 23 or hour < 5:
            self._trigger_callback("late_night", {"hour": hour})

        # --- System resources ---
        cpu = snapshot.get("cpu_percent", 0)
        ram = snapshot.get("ram_percent", 0)
        if cpu > 80 or ram > 85:
            self._trigger_callback("system_resources", {
                "cpu": f"{cpu:.0f}",
                "ram": f"{ram:.0f}",
                "window": snapshot.get("active_window", "Unknown"),
            })

        self._last_window = current_window

    def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self._flush_interval)
            with self._buffer_lock:
                if self._event_buffer:
                    self._flush_events()

    def _flush_events(self) -> None:
        if not self._event_buffer:
            return
        batch = self._event_buffer.copy()
        self._event_buffer.clear()
        try:
            self._memory_manager.log_interactions_batch(batch)
        except Exception:
            logger.warning("Failed to flush event batch", exc_info=True)
            self._event_buffer.extend(batch)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        with self._buffer_lock:
            if self._event_buffer:
                self._flush_events()
        if self._thread:
            self._thread.join(timeout=1)
        if self._flush_thread:
            self._flush_thread.join(timeout=1)
        logger.info("EventMonitor stopped")

    def get_latest(self) -> Dict | None:
        with self._lock:
            return dict(self._latest_snapshot) if self._latest_snapshot else None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def window_monitoring_enabled(self) -> bool:
        return bool(self._config.get("privacy", {}).get("monitor_active_window", True))
