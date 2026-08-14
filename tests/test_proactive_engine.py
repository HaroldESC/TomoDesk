import tempfile
import time
from pathlib import Path

import pytest
import yaml

from src.personality.comment_loader import CommentLoader
from src.memory.memory import MemoryManager
from src.llm.proactive_engine import ProactiveEngine
from src.llm.proactive_policy import ProactivePolicy


def make_config() -> dict:
    return {
        "modes": {
            "proactive_comments": True,
            "proactive_cooldown_seconds": 0,
            "max_comments_per_hour": 100,
            "comment_probability": 1.0,
        },
        "personality": {"name": "Tomo"},
    }


def make_comment_loader(persist_dir) -> CommentLoader:
    data = {
        "greeting": ["Hello {name}!", "Hi there!"],
        "farewell": ["Goodbye {name}!"],
        "session_start": ["Session started!"],
        "idle_long": ["You were idle for {idle_minutes} minutes."],
        "app_opened": ["You opened {window}."],
        "random": ["Random comment!"],
    }
    path = Path(persist_dir) / "comments_test.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return CommentLoader(str(path))


def test_handle_trigger_returns_phrase(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    result = engine.handle_trigger("farewell")
    assert result is not None
    assert "Tomo" in result


def test_handle_trigger_suppressed(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    policy.set_dnd_mode(True)
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    result = engine.handle_trigger("greeting")
    assert result is None


def test_handle_trigger_no_category(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    result = engine.handle_trigger("nonexistent")
    assert result is None


def test_handle_trigger_with_context(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    result = engine.handle_trigger("app_opened", {"window": "Chrome"})
    assert result is not None
    assert "Chrome" in result


def test_handle_trigger_with_idle_context(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    result = engine.handle_trigger("idle_long", {"idle_minutes": "15"})
    assert result is not None
    assert "15" in result


def test_delivery_callback(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())

    received = []

    def callback(comment, trigger_type):
        received.append((comment, trigger_type))

    engine.set_delivery_callback(callback)
    engine.handle_trigger("farewell")
    assert len(received) == 1
    assert received[0][1] == "farewell"


def test_get_stats(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    stats = engine.get_stats()
    assert stats["enabled"] is True


def test_stop_random_timer_returns_quickly_while_sleeping(tmp_path, memory_manager):
    loader = make_comment_loader(tmp_path)
    policy = ProactivePolicy(make_config())
    engine = ProactiveEngine(loader, policy, memory_manager, make_config())
    engine.start_random_timer()

    time.sleep(0.05)

    start = time.monotonic()
    engine.stop_random_timer()
    elapsed = time.monotonic() - start

    assert elapsed < 0.5
