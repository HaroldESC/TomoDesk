import logging
from unittest.mock import patch

import pytest

from src.memory.chroma_manager import ChromaManager
from src.memory.database import DatabaseManager
from src.memory.memory import MemoryManager

from tests.mock_chroma import MockChroma


def test_chroma_manager_initialize_catches_exception(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    cm = ChromaManager(tmp_path / "chroma", "all-MiniLM-L6-v2")

    with patch.object(cm, "_persist_path") as mock_path:
        mock_path.mkdir.side_effect = PermissionError("no access")
        cm.initialize()

    assert any("Failed to initialize ChromaDB" in msg for msg in caplog.messages)


def test_chroma_manager_add_catches_exception(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    cm = ChromaManager(tmp_path / "chroma", "all-MiniLM-L6-v2")
    cm.initialize()

    cm._collections = {}
    cm.add_to_collection("memories", ["doc"], [{}], ["id1"])

    assert any("add_to_collection failed" in msg for msg in caplog.messages)


def test_chroma_manager_query_returns_empty_on_error(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    cm = ChromaManager(tmp_path / "chroma", "all-MiniLM-L6-v2")
    cm.initialize()

    cm._collections = {}
    results = cm.query_collection("memories", "test", n_results=5)

    assert results == []
    assert any("query_collection failed" in msg for msg in caplog.messages)


def test_chroma_manager_delete_catches_exception(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    cm = ChromaManager(tmp_path / "chroma", "all-MiniLM-L6-v2")
    cm.initialize()

    cm._collections = {}
    cm.delete_from_collection("memories", ["id1"])

    assert any("delete_from_collection failed" in msg for msg in caplog.messages)


def test_chroma_manager_count_returns_zero_on_error(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    cm = ChromaManager(tmp_path / "chroma", "all-MiniLM-L6-v2")
    cm.initialize()

    cm._collections = {}
    count = cm.count("memories")

    assert count == 0
    assert any("count failed" in msg for msg in caplog.messages)


def test_memory_manager_sqlite_still_works_when_chroma_fails(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize()

    chroma = MockChroma(fail_add=True, fail_query=True, fail_delete=True)
    mem = MemoryManager(db, chroma, {"memory": {"max_short_term_messages": 5}})

    mem.add_long_term_memory("test", "fact", 0.5)
    results = mem.query_memories("test", n=5)
    assert results == []

    note_id = mem.add_note("Title", "Content")
    assert mem.get_note(note_id) is not None

    rem_id = mem.add_reminder("Test", "2000-01-01 00:00:00")
    due = mem.get_due_reminders()
    assert rem_id in [r["id"] for r in due]

    mem.add_episodic_memory("Episode", 0.8, "manual")
    logs = mem.list_episodic_log()
    assert len(logs) == 1


def test_memory_manager_recovers_after_chroma_error(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize()

    chroma = MockChroma()
    mem = MemoryManager(db, chroma, {"memory": {"max_short_term_messages": 5}})

    chroma.fail_add = True
    mem.add_long_term_memory("lost", "fact", 0.5)
    chroma.fail_add = False

    doc_id = mem.add_long_term_memory("recovered", "fact", 0.5)
    results = mem.query_memories("recovered", n=5)
    assert len(results) > 0


def test_add_long_term_memory_handles_chroma_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize()
    chroma = MockChroma(fail_add=True)
    mem = MemoryManager(db, chroma, {"memory": {"max_short_term_messages": 5}})

    mem.add_long_term_memory("Test content", "fact", 0.5)

    results = mem.query_memories("Test", n=5)
    assert results == []


def test_episodic_memory_add_handles_chroma_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = DatabaseManager(db_path)
    db.initialize()
    chroma = MockChroma(fail_add=True)
    mem = MemoryManager(db, chroma, {"memory": {"max_short_term_messages": 5}})

    doc_id = mem.add_episodic_memory("Test summary", 0.8, "manual")
    assert doc_id is not None

    logs = mem.list_episodic_log()
    assert len(logs) == 1
    assert logs[0]["summary"] == "Test summary"
