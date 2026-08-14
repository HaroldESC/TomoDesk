import time

import pytest


def test_add_episodic_memory(memory_manager):
    doc_id = memory_manager.add_episodic_memory(
        "Started the TomoDesk project",
        importance_score=0.9,
        source="manual"
    )
    assert doc_id is not None
    assert doc_id.startswith("episodic_")

    logs = memory_manager.list_episodic_log()
    assert len(logs) == 1
    assert logs[0]["summary"] == "Started the TomoDesk project"
    assert logs[0]["importance_score"] == 0.9
    assert logs[0]["source"] == "manual"


def test_query_episodic(memory_manager):
    memory_manager.add_episodic_memory("I love coffee", importance_score=0.5)
    memory_manager.add_episodic_memory("Started learning Python", importance_score=0.8)
    memory_manager.add_episodic_memory("Bought a new monitor", importance_score=0.3)

    results = memory_manager.query_episodic("programming language", n=3)
    assert any("Python" in r.get("document", "") for r in results)


def test_delete_episodic_memory(memory_manager):
    memory_manager.add_episodic_memory("Test memory to delete", importance_score=0.5)
    logs = memory_manager.list_episodic_log()
    assert len(logs) == 1

    success = memory_manager.delete_episodic_memory(logs[0]["id"])
    assert success is True

    logs = memory_manager.list_episodic_log()
    assert len(logs) == 0


def test_list_episodic_log_ordered(memory_manager):
    memory_manager.add_episodic_memory("First memory", importance_score=0.5)
    time.sleep(1.01 - time.time() % 1.0)
    memory_manager.add_episodic_memory("Second memory", importance_score=0.7)

    logs = memory_manager.list_episodic_log()
    assert len(logs) == 2
    assert "Second" in logs[0]["summary"]


def test_query_episodic_relevance(memory_manager):
    memory_manager.add_episodic_memory("Went to the beach last summer", importance_score=0.3)
    memory_manager.add_episodic_memory("Started TomoDesk development in June", importance_score=0.9)

    results = memory_manager.query_episodic("coding project", n=3)
    assert results
    assert any("TomoDesk" in r.get("document", "") for r in results)
