import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.core.events import EventMonitor, SystemMonitor


SNAPSHOT = {
    "timestamp": "2024-01-01T00:00:00",
    "active_window": "Code",
    "idle_time_seconds": 10,
    "cpu_percent": 25.0,
    "ram_percent": 45.0,
}


class TestSystemMonitor:
    @pytest.fixture(autouse=True)
    def _mock_os(self):
        with patch("src.core.events.gw") as gw:
            gw.getActiveWindow.return_value = MagicMock(title="Code")
            with patch("src.core.events._get_idle_time_ms", return_value=10000):
                with patch("src.core.events.psutil.cpu_percent", return_value=25.0):
                    with patch("src.core.events.psutil.virtual_memory") as vm:
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
