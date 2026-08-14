from unittest.mock import MagicMock

import pytest

from src.core.context import ContextBuilder


@pytest.fixture
def config():
    return {
        "personality": {
            "name": "Tomo",
            "traits": "friendly, curious, helpful",
        }
    }


@pytest.fixture
def memory_manager():
    return MagicMock()


def test_build_context_with_snapshot(config, memory_manager):
    event_monitor = MagicMock()
    event_monitor.get_latest.return_value = {
        "active_window": "Visual Studio Code",
        "idle_time_seconds": 125,
        "cpu_percent": 15.3,
        "ram_percent": 62.7,
    }
    builder = ContextBuilder(config, memory_manager, event_monitor)
    context = builder.build_context()

    assert "Time:" in context
    assert "Active window:" in context
    assert "Idle:" in context
    assert "System:" in context
    assert "None" not in context
    assert "Visual Studio Code" in context
    assert "2m 5s" in context
    assert "15.3%" in context
    assert "62.7%" in context


def test_build_context_no_snapshot(config, memory_manager):
    event_monitor = MagicMock()
    event_monitor.get_latest.return_value = None
    builder = ContextBuilder(config, memory_manager, event_monitor)
    context = builder.build_context()

    assert "Unknown" in context
    assert "0m 0s" in context
    assert "CPU 0.0%" in context
    assert "RAM 0.0%" in context


def test_build_system_message_without_emotion(config, memory_manager):
    builder = ContextBuilder(config, memory_manager)
    msg = builder.build_system_message()

    assert "You are Tomo" in msg
    assert "friendly, curious, helpful" in msg
    assert "Emotional state:" not in msg


def test_build_system_message_with_emotion(config, memory_manager):
    builder = ContextBuilder(config, memory_manager)
    emotional_state = {
        "happiness": 0.7,
        "energy": 0.4,
        "curiosity": 0.6,
        "closeness": 0.3,
        "connection": 0.5,
    }
    msg = builder.build_system_message(emotional_state)

    assert "You are Tomo" in msg
    assert "Emotional state:" in msg
    assert "happiness=0.7" in msg
    assert "energy=0.4" in msg
    assert "curiosity=0.6" in msg
    assert "closeness=0.3" in msg
    assert "connection=0.5" in msg


def test_build_context_hides_active_window_when_disabled(config, memory_manager):
    event_monitor = MagicMock()
    event_monitor.get_latest.return_value = {
        "active_window": "Code",
        "idle_time_seconds": 10,
        "cpu_percent": 5.0,
        "ram_percent": 30.0,
    }
    disabled_config = dict(config)
    disabled_config["privacy"] = {"monitor_active_window": False}
    builder = ContextBuilder(disabled_config, memory_manager, event_monitor)
    context = builder.build_context()
    assert "Active window:" not in context
    assert "Code" not in context


def test_build_context_has_active_window_when_enabled(config, memory_manager):
    event_monitor = MagicMock()
    event_monitor.get_latest.return_value = {
        "active_window": "Code",
        "idle_time_seconds": 10,
        "cpu_percent": 5.0,
        "ram_percent": 30.0,
    }
    enabled_config = dict(config)
    enabled_config["privacy"] = {"monitor_active_window": True}
    builder = ContextBuilder(enabled_config, memory_manager, event_monitor)
    context = builder.build_context()
    assert "Active window: Code" in context
