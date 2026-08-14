import pytest

from src.memory.database import DatabaseManager
from src.memory.memory import MemoryManager

from tests.mock_chroma import MockChroma


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test_tomodesk.db"
    db = DatabaseManager(db_path)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def mem(db):
    config = {"memory": {"max_short_term_messages": 20}}
    chroma = MockChroma()
    return MemoryManager(db, chroma, config)


def test_initialize_creates_all_tables(mem):
    mem.set_preference("test_key", "test_value")
    assert mem.get_preference("test_key") == "test_value"

    note_id = mem.add_note("Title", "Content")
    notes = mem.list_notes()
    assert any(n["id"] == note_id for n in notes)

    rem_id = mem.add_reminder("Reminder", "2026-12-31 23:59:59")
    reminders = mem.list_reminders()
    assert any(r["id"] == rem_id for r in reminders)

    mem.log_interaction("user_message", {"text": "hello"})

    doc_id = mem.add_episodic_memory("Summary", 0.8, "manual")
    logs = mem.list_episodic_log()
    assert any(l["summary"] == "Summary" for l in logs)


def test_user_profile_key_value(mem):
    assert mem.get_preference("name") == "User"
    assert mem.get_preference("language") == "es"

    mem.set_preference("name", "TestUser")
    assert mem.get_preference("name") == "TestUser"


def test_insert_and_read_note(mem):
    note_id = mem.add_note("Test Note", "This is content", "test,important")
    note = mem.get_note(note_id)
    assert note["title"] == "Test Note"
    assert note["content"] == "This is content"
    assert note["tags"] == "test,important"


def test_insert_and_read_reminder(mem):
    rem_id = mem.add_reminder("Test reminder", "2026-12-31 23:59:59")
    reminders = mem.list_reminders()
    match = [r for r in reminders if r["id"] == rem_id]
    assert len(match) == 1
    assert match[0]["active"] == 1
    assert match[0]["trigger_time"] == "2026-12-31 23:59:59"


def test_insert_and_read_interaction(mem):
    mem.log_interaction("user_message", {"text": "hello"})
    mem.log_interaction("system_event", {"event": "startup"})

    mem2 = mem  # reuse to verify no crash on second call
    mem2.log_interaction("user_message", {"text": "again"})


def test_insert_and_read_episodic_log(mem):
    doc_id = mem.add_episodic_memory("Test summary", 0.8, "manual")
    logs = mem.list_episodic_log()
    match = [l for l in logs if l["summary"] == "Test summary"]
    assert len(match) == 1
    assert match[0]["importance_score"] == 0.8
    assert match[0]["source"] == "manual"


class TestBatchInteractionLog:
    def test_batch_empty(self, mem):
        mem.log_interactions_batch([])

    def test_batch_single_event(self, mem):
        mem.log_interactions_batch([("test_event", {"key": "value"})])
        conn = mem._db._get_connection()
        rows = conn.execute("SELECT * FROM interaction_log WHERE event_type = 'test_event'").fetchall()
        assert len(rows) == 1
        assert '"key": "value"' in rows[0]["data_json"]

    def test_batch_multiple_events(self, mem):
        events = [(f"event_{i}", {"num": i}) for i in range(10)]
        mem.log_interactions_batch(events)
        conn = mem._db._get_connection()
        rows = conn.execute("SELECT * FROM interaction_log").fetchall()
        assert len(rows) >= 10

    def test_batch_with_none_data(self, mem):
        mem.log_interactions_batch([("no_data", None)])
        conn = mem._db._get_connection()
        rows = conn.execute("SELECT * FROM interaction_log WHERE event_type = 'no_data'").fetchall()
        assert len(rows) == 1
        assert rows[0]["data_json"] is None

    def test_batch_preserves_event_order(self, mem):
        events = [(f"order_{i}", {"pos": i}) for i in range(5)]
        mem.log_interactions_batch(events)
        conn = mem._db._get_connection()
        rows = conn.execute(
            "SELECT event_type FROM interaction_log WHERE event_type LIKE 'order_%' ORDER BY id"
        ).fetchall()
        types = [r["event_type"] for r in rows]
        assert types == ["order_0", "order_1", "order_2", "order_3", "order_4"]


class TestExecuteMany:
    def test_execute_many_basic(self, db):
        db.execute_many(
            "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
            [("a", None), ("b", None)],
        )
        db.commit()
        rows = db.execute("SELECT * FROM interaction_log").fetchall()
        assert len(rows) == 2

    def test_execute_many_empty(self, db):
        db.execute_many("INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)", [])
        db.commit()

    def test_execute_many_large_batch(self, db):
        params = [(f"bulk_{i}", f'{{"n": {i}}}') for i in range(100)]
        db.execute_many(
            "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
            params,
        )
        db.commit()
        rows = db.execute("SELECT * FROM interaction_log").fetchall()
        assert len(rows) == 100
