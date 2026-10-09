import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.events import EventMonitor, SystemMonitor
from src.platform import WindowInfo


SNAPSHOT = {
    "timestamp": "2024-01-01T00:00:00",
    "active_window": "Code",
    "idle_time_seconds": 10,
    "cpu_percent": 25.0,
    "ram_percent": 45.0,
}


class TestSystemMonitor:
    @pytest.fixture
    def adapter(self):
        adapter = MagicMock()
        adapter.get_active_window.return_value = WindowInfo(
            "Code", (0, 0, 100, 100), None, False, False
        )
        adapter.get_idle_time_ms.return_value = 10000
        return adapter

    @pytest.fixture(autouse=True)
    def _mock_os(self, adapter):
        with patch("src.core.events.get_platform", return_value=adapter):
            with patch("psutil.cpu_percent", return_value=25.0):
                with patch("psutil.virtual_memory") as vm:
                    vm.return_value.percent = 45.0
                    yield

    def test_system_monitor_poll(self):
        monitor = SystemMonitor()
        snapshot = monitor.poll()
        assert isinstance(snapshot, dict)
        required_keys = [
            "timestamp",
            "active_window",
            "idle_time_seconds",
            "cpu_percent",
            "ram_percent",
        ]
        for key in required_keys:
            assert key in snapshot, f"Missing key: {key}"
        assert isinstance(snapshot["active_window"], str)
        assert isinstance(snapshot["idle_time_seconds"], int)
        assert snapshot["idle_time_seconds"] == 10
        assert isinstance(snapshot["cpu_percent"], float)
        assert isinstance(snapshot["ram_percent"], float)
        assert 0.0 <= snapshot["ram_percent"] <= 100.0

    def test_system_monitor_privacy_disabled(self):
        monitor = SystemMonitor(config={"privacy": {"monitor_active_window": False}})
        snapshot = monitor.poll()
        assert snapshot["active_window"] == "Unknown"

    def test_system_monitor_default_returns_window_title(self):
        monitor = SystemMonitor()
        snapshot = monitor.poll()
        assert snapshot["active_window"] == "Code"

    def test_system_monitor_unknown_when_no_active_window(self, adapter):
        adapter.get_active_window.return_value = None
        snapshot = SystemMonitor().poll()
        assert snapshot["active_window"] == "Unknown"


class TestEventMonitor:
    @pytest.fixture
    def memory_manager(self):
        return MagicMock()

    @pytest.fixture(autouse=True)
    def _mock_system_monitor(self):
        with patch("src.core.events.SystemMonitor") as cls:
            instance = cls.return_value
            instance.poll.return_value = SNAPSHOT
            yield

    def test_event_monitor_start_stop(self, memory_manager, tmp_path):
        config = {"dummy": True}
        monitor = EventMonitor(memory_manager, config, poll_interval=0.05)
        monitor.start()
        assert monitor.is_running is True
        time.sleep(0.15)
        latest = monitor.get_latest()
        assert latest is not None, "EventMonitor should have collected data after 1s"
        assert "active_window" in latest
        assert "cpu_percent" in latest
        monitor.stop()
        assert monitor.is_running is False

    def test_events_logged_to_interaction_log(self, memory_manager, tmp_path):
        real_memory = MagicMock()

        monitor = EventMonitor(real_memory, {}, poll_interval=0.05)
        monitor._flush_interval = 0.1
        monitor.start()
        time.sleep(0.25)
        monitor.stop()

        assert real_memory.log_interactions_batch.call_count >= 1
        call = real_memory.log_interactions_batch.call_args_list[0]
        events = call[0][0]
        assert len(events) >= 1
        event_type, data = events[0]
        assert event_type == "system_event"
        assert "active_window" in data

    def test_buffer_flushes_on_max_size(self, memory_manager, tmp_path):
        real_memory = MagicMock()
        monitor = EventMonitor(real_memory, {}, poll_interval=0.01)
        monitor._max_buffer_size = 5
        monitor._flush_interval = 999
        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        assert real_memory.log_interactions_batch.call_count >= 1

    def test_buffer_flushes_on_stop(self, memory_manager, tmp_path):
        real_memory = MagicMock()
        monitor = EventMonitor(real_memory, {}, poll_interval=0.02)
        monitor._flush_interval = 999
        monitor.start()
        time.sleep(0.1)
        assert real_memory.log_interactions_batch.call_count == 0
        monitor.stop()
        assert real_memory.log_interactions_batch.call_count >= 1

    def test_buffer_accumulates_events(self, memory_manager, tmp_path):
        real_memory = MagicMock()
        monitor = EventMonitor(real_memory, {}, poll_interval=0.02)
        monitor._flush_interval = 999
        monitor._max_buffer_size = 100
        monitor.start()
        time.sleep(0.15)
        with monitor._buffer_lock:
            buffered = len(monitor._event_buffer)
        assert buffered >= 1
        monitor.stop()

    def test_stop_returns_quickly_while_threads_sleeping(self, memory_manager, tmp_path):
        real_memory = MagicMock()
        monitor = EventMonitor(real_memory, {}, poll_interval=60.0)
        monitor._flush_interval = 60.0
        monitor.start()
        time.sleep(0.05)

        start = time.monotonic()
        monitor.stop()
        elapsed = time.monotonic() - start

        assert monitor.is_running is False
        assert elapsed < 0.5


class TestTriggerGuards:
    """Los triggers por contexto se disparan una sola vez, no en cada poll."""

    def _make(self, window, **overrides):
        snapshot = dict(SNAPSHOT, active_window=window, **overrides)
        triggers = []
        monitor = EventMonitor(MagicMock(), {})
        monitor._trigger_callback = lambda t, p: triggers.append(t)
        monitor._check_triggers(snapshot)
        monitor._check_triggers(snapshot)
        monitor._check_triggers(snapshot)
        return triggers

    def test_music_detected_fires_once_per_window(self):
        triggers = self._make("Spotify Premium")
        assert triggers.count("music_detected") == 1

    def test_coding_detected_fires_once_per_window(self):
        triggers = self._make("main.py - Visual Studio Code")
        assert triggers.count("coding_detected") == 1

    def test_switching_window_refires(self):
        triggers = []
        monitor = EventMonitor(MagicMock(), {})
        monitor._trigger_callback = lambda t, p: triggers.append(t)
        monitor._check_triggers(dict(SNAPSHOT, active_window="Spotify"))
        monitor._check_triggers(dict(SNAPSHOT, active_window="Chrome"))
        monitor._check_triggers(dict(SNAPSHOT, active_window="Spotify"))
        assert triggers.count("music_detected") == 2

    def test_late_night_fires_once_per_streak(self):
        with patch("src.core.events.datetime") as dt:
            dt.now.return_value = MagicMock(hour=23)
            triggers = self._make("Chrome")
        assert triggers.count("late_night") == 1

    def test_resources_fire_once_until_they_drop(self):
        triggers = self._make("Chrome", cpu_percent=95.0, ram_percent=95.0)
        assert triggers.count("system_resources") == 1

    def test_resources_refire_after_recovering(self):
        triggers = []
        monitor = EventMonitor(MagicMock(), {})
        monitor._trigger_callback = lambda t, p: triggers.append(t)
        monitor._check_triggers(dict(SNAPSHOT, cpu_percent=95.0))
        monitor._check_triggers(dict(SNAPSHOT, cpu_percent=10.0))
        monitor._check_triggers(dict(SNAPSHOT, cpu_percent=95.0))
        assert triggers.count("system_resources") == 2


class TestTriggerKeywords:
    """Los terminos no deben coincidir con substrings genericos."""

    def _matches(self, window):
        from src.core.events import _CODING_TERMS, _MUSIC_TERMS, _matches_any

        return (
            _matches_any(window.lower(), _MUSIC_TERMS),
            _matches_any(window.lower(), _CODING_TERMS),
        )

    def test_unicode_is_not_coding(self):
        music, coding = self._matches("Unicode Character Table")
        assert (music, coding) == (False, False)

    def test_cmdline_is_not_coding(self):
        music, coding = self._matches("build-cmdline-output.txt - Notepad")
        assert coding is False

    def test_music_substring_word_still_matches(self):
        music, coding = self._matches("Apple Music")
        assert music is True

    def test_real_editors_match(self):
        for title in ("Visual Studio Code", "vim", "Neovim", "PyCharm",
                      "Terminal", "IntelliJ IDEA"):
            _music, coding = self._matches(title)
            assert coding is True, title

    def test_spotify_matches_music(self):
        music, _coding = self._matches("Spotify")
        assert music is True
