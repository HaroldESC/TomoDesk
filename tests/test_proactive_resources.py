import time
from unittest.mock import Mock

from src.core.events import EventMonitor


def test_resource_trigger_fires(mocker):
    mock_memory = mocker.Mock()
    mocker.patch("src.core.events.SystemMonitor.poll", return_value={
        "timestamp": "2026-06-08T00:00:00",
        "active_window": "Test App",
        "idle_time_seconds": 10,
        "cpu_percent": 85.0,
        "ram_percent": 60.0,
    })

    config = {
        "modes": {
            "proactive_comments": True,
            "proactive_cooldown_seconds": 0,
            "max_comments_per_hour": 100,
            "comment_probability": 1.0,
        },
        "memory": {"max_short_term_messages": 20},
    }

    monitor = EventMonitor(mock_memory, config, poll_interval=0.05)
    triggers = []
    monitor.set_trigger_callback(lambda t, ctx: triggers.append((t, ctx)))
    monitor.start()
    time.sleep(0.1)
    monitor.stop()

    assert any(t == "system_resources" for t, _ in triggers)


def test_resource_trigger_does_not_fire_when_low(mocker):
    mock_memory = mocker.Mock()
    mocker.patch("src.core.events.SystemMonitor.poll", return_value={
        "timestamp": "2026-06-08T00:00:00",
        "active_window": "Test App",
        "idle_time_seconds": 10,
        "cpu_percent": 45.0,
        "ram_percent": 50.0,
    })

    config = {
        "modes": {"proactive_comments": True},
        "memory": {"max_short_term_messages": 20},
    }

    monitor = EventMonitor(mock_memory, config, poll_interval=0.05)
    triggers = []
    monitor.set_trigger_callback(lambda t, ctx: triggers.append((t, ctx)))
    monitor.start()
    time.sleep(0.1)
    monitor.stop()

    assert not any(t == "system_resources" for t, _ in triggers)
