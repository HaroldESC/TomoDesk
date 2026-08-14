import threading
import time

import pytest

from src.memory.database import DatabaseManager
from src.llm.proactive_policy import ProactivePolicy
from src.core.state import StateManager


def _state_config():
    return {"personality": {}}


def _proactive_config():
    return {
        "modes": {
            "proactive_comments": True,
            "proactive_cooldown_seconds": 0,
            "max_comments_per_hour": 100,
            "comment_probability": 1.0,
        }
    }


def test_state_manager_concurrent_updates():
    sm = StateManager(_state_config())
    N = 50
    errors = []

    def worker():
        try:
            for _ in range(50):
                sm.update("positive_feedback", intensity=0.5)
                sm.get_state()
                sm.get_prompt_instruction()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = sm.get_state()
    assert not errors, f"Thread safety errors: {errors}"
    assert 0.0 <= state["happiness"] <= 1.0
    assert 0.0 <= state["energy"] <= 1.0


def test_state_manager_concurrent_reads_during_writes():
    sm = StateManager(_state_config())
    N = 30
    errors = []

    def writer():
        try:
            for _ in range(30):
                sm.update("user_message", intensity=0.3)
                sm.update("long_conversation", intensity=0.5)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(30):
                s = sm.get_state()
                assert "happiness" in s
                sm.get("closeness")
                sm.get_prompt_instruction()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer) for _ in range(N // 2)]
    threads += [threading.Thread(target=reader) for _ in range(N // 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"


def test_database_manager_concurrent_writes(tmp_path):
    db_path = tmp_path / "test_concurrent.db"
    db = DatabaseManager(db_path)
    db.initialize()
    N = 20
    errors = []

    def writer():
        try:
            for i in range(20):
                db.execute(
                    "INSERT INTO notes (title, content) VALUES (?, ?)",
                    (f"Thread title {i}", "content"),
                )
                db.commit()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    cursor = db.execute("SELECT COUNT(*) AS cnt FROM notes")
    count = cursor.fetchone()["cnt"]
    db.close()

    assert not errors, f"Database thread safety errors: {errors}"
    assert count == N * 20


def test_database_manager_concurrent_reads_during_writes(tmp_path):
    db_path = tmp_path / "test_concurrent_rw.db"
    db = DatabaseManager(db_path)
    db.initialize()
    db.execute("INSERT INTO notes (title, content) VALUES ('initial', 'content')")
    db.commit()

    N = 20
    errors = []

    def writer():
        try:
            for i in range(20):
                db.execute(
                    "INSERT INTO notes (title, content) VALUES (?, ?)",
                    (f"note {i}", "data"),
                )
                db.commit()
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(20):
                c = db.execute("SELECT COUNT(*) AS cnt FROM notes")
                c.fetchone()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer) for _ in range(N)]
    threads += [threading.Thread(target=reader) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    db.close()
    assert not errors, f"Database RW thread safety errors: {errors}"


def test_proactive_policy_concurrent():
    policy = ProactivePolicy(_proactive_config())
    N = 20
    errors = []

    def worker():
        try:
            for _ in range(50):
                policy.can_comment("generic")
                if policy.can_comment("generic"):
                    policy.record_comment()
                policy.get_stats()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = policy.get_stats()
    assert not errors, f"Policy thread safety errors: {errors}"
    assert stats["comments_this_hour"] > 0


def test_proactive_policy_focus_during_checks():
    policy = ProactivePolicy(_proactive_config())
    errors = []

    def checker():
        try:
            for _ in range(100):
                if policy.can_comment("generic"):
                    policy.record_comment()
        except Exception as e:
            errors.append(e)

    def toggler():
        try:
            for _ in range(50):
                policy.set_focus_mode(True)
                policy.set_focus_mode(False)
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=checker)
    t2 = threading.Thread(target=toggler)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Policy focus toggle errors: {errors}"
