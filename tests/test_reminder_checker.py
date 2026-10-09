import datetime
import time

import pytest

from src.memory.database import DatabaseManager
from src.memory.memory import MemoryManager
from src.system.reminder_checker import ReminderChecker

from tests.mock_chroma import MockChroma


@pytest.fixture
def memory_manager(tmp_path):
    db_path = tmp_path / "test.db"

    db_manager = DatabaseManager(str(db_path))
    db_manager.initialize()
    chroma = MockChroma()

    return MemoryManager(
        db_manager, chroma, {"memory": {"max_short_term_messages": 20}}
    )


def test_reminder_checker_triggers_callback(memory_manager):
    trigger_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory_manager.add_reminder("Test reminder", trigger_time)

    callback_calls = []

    def callback(msg):
        callback_calls.append(msg)

    checker = ReminderChecker(memory_manager, {}, check_interval=0.3)
    checker.set_callback(callback)
    checker.start()

    time.sleep(0.4)

    checker.stop()

    assert len(callback_calls) >= 1
    assert "Test reminder" in callback_calls[0]


def test_stop_returns_quickly_while_thread_sleeping(memory_manager):
    checker = ReminderChecker(memory_manager, {}, check_interval=60.0)
    checker.start()

    time.sleep(0.05)

    start = time.monotonic()
    checker.stop()
    elapsed = time.monotonic() - start

    assert checker.is_running is False
    assert elapsed < 0.5


def test_due_reminder_is_not_consumed_without_callback(memory_manager):
    """Sin callback el recordatorio debe seguir pendiente.

    Regresion: el checker desactivaba el recordatorio pese a no haberlo
    entregado, asi que desaparecia sin mostrarse nunca.
    """
    trigger_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory_manager.add_reminder("Undelivered", trigger_time)

    checker = ReminderChecker(memory_manager, {}, check_interval=0.1)
    checker.start()
    time.sleep(0.35)
    still_running = checker.is_running
    checker.stop()

    assert still_running is True
    reminders = memory_manager.list_reminders()
    assert [r["message"] for r in reminders] == ["Undelivered"]
    # No se registro como disparado en el log de interacciones.
    logged = [
        e for e in memory_manager.list_episodic_log()
        if e.get("source") == "reminder_triggered"
    ]
    assert logged == []


def test_reminder_is_delivered_after_callback_is_wired_late(memory_manager):
    """El recordatorio se entrega en cuanto haya callback, no se pierde."""
    trigger_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    memory_manager.add_reminder("Late wiring", trigger_time)

    checker = ReminderChecker(memory_manager, {}, check_interval=0.1)
    checker.start()
    time.sleep(0.25)  # ciclos sin callback

    calls = []
    checker.set_callback(lambda msg: calls.append(msg))
    time.sleep(0.35)
    checker.stop()

    assert calls == ["Late wiring"]
    assert memory_manager.list_reminders() == []
