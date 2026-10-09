import time
from unittest.mock import MagicMock

from main import _graceful_shutdown, _ShutdownState


def _slow_summary():
    time.sleep(1.0)
    return []


def make_deps():
    deps = {
        "proactive_engine": MagicMock(),
        "reminder_checker": MagicMock(),
        "event_monitor": MagicMock(),
        "engine": MagicMock(),
        "state_manager": MagicMock(),
        "memory_manager": MagicMock(),
    }
    deps["engine"].summarize_session.side_effect = _slow_summary
    return deps


def test_preferences_saved_once_on_double_shutdown():
    deps = make_deps()
    state = _ShutdownState()
    _graceful_shutdown(deps, state)
    _graceful_shutdown(deps, state)
    assert deps["state_manager"].save_to_preferences.call_count == 1
    assert deps["engine"].summarize_session.call_count == 1


def test_shutdown_waits_bounded_time_for_summary():
    deps = make_deps()
    start = time.monotonic()
    _graceful_shutdown(deps, _ShutdownState())
    elapsed = time.monotonic() - start
    assert elapsed < 1.0


def test_shutdown_does_not_mutate_deps():
    """deps is splatted into MainWindow, so it must stay clean."""
    deps = make_deps()
    before = set(deps)
    _graceful_shutdown(deps, _ShutdownState())
    assert set(deps) == before
    assert not any(k.startswith("_") for k in deps)
