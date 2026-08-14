import pytest

from src.memory.database import DatabaseManager
from src.memory.memory import MemoryManager

from tests.mock_chroma import MockChroma


@pytest.fixture
def memory(tmp_path):
    db_path = tmp_path / "test_tomodesk.db"

    db = DatabaseManager(db_path)
    db.initialize()

    chroma = MockChroma()

    config = {
        "memory": {"max_short_term_messages": 5},
    }
    mem = MemoryManager(db, chroma, config)
    yield mem


class TestShortTerm:
    def test_add_and_get_messages(self, memory):
        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi there")
        msgs = memory.get_recent_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "Hi there"

    def test_fifo_truncation(self, memory):
        for i in range(10):
            memory.add_message("user", f"Message {i}")
        msgs = memory.get_recent_messages()
        assert len(msgs) == 5
        assert msgs[0]["content"] == "Message 5"

    def test_clear(self, memory):
        memory.add_message("user", "test")
        memory.clear_short_term()
        assert memory.get_recent_messages() == []

    def test_get_n_recent(self, memory):
        for i in range(5):
            memory.add_message("user", str(i))
        msgs = memory.get_recent_messages(2)
        assert len(msgs) == 2
        assert msgs[-1]["content"] == "4"


class TestNotes:
    def test_crud(self, memory):
        note_id = memory.add_note("Title", "Content", "tag1,tag2")
        note = memory.get_note(note_id)
        assert note["title"] == "Title"
        assert note["tags"] == "tag1,tag2"

        memory.update_note(note_id, title="Updated Title")
        note = memory.get_note(note_id)
        assert note["title"] == "Updated Title"

        notes = memory.list_notes()
        assert len(notes) >= 1

        memory.delete_note(note_id)
        assert memory.get_note(note_id) is None

    def test_list_notes_order(self, memory):
        memory.add_note("Second", "content")
        memory.add_note("First", "content")
        notes = memory.list_notes()
        assert notes[0]["title"] == "First"


class TestReminders:
    def test_create_and_due(self, memory):
        rid = memory.add_reminder("Test", "2000-01-01 00:00:00")
        due = memory.get_due_reminders()
        ids = [r["id"] for r in due]
        assert rid in ids

    def test_deactivate(self, memory):
        rid = memory.add_reminder("Test", "2000-01-01 00:00:00")
        memory.deactivate_reminder(rid)
        due = memory.get_due_reminders()
        assert rid not in [r["id"] for r in due]

    def test_list_reminders(self, memory):
        memory.add_reminder("R1", "2099-01-01 00:00:00")
        memory.add_reminder("R2", "2000-01-01 00:00:00", "daily")
        all_active = memory.list_reminders(active_only=True)
        assert len(all_active) == 2


class TestInteractionLog:
    def test_log(self, memory):
        memory.log_interaction("user_message", {"text": "hello"})
        memory.log_interaction("system_event")
        conn = memory._db._get_connection()
        cursor = conn.execute("SELECT * FROM interaction_log")
        rows = cursor.fetchall()
        assert len(rows) == 2


class TestUserProfile:
    def test_set_and_get(self, memory):
        memory.set_preference("theme", "dark")
        assert memory.get_preference("theme") == "dark"

        memory.set_preference("theme", "light")
        assert memory.get_preference("theme") == "light"

    def test_default_values(self, memory):
        assert memory.get_preference("name") == "User"
        assert memory.get_preference("language") == "es"


class TestChromaOperations:
    def test_long_term_memory(self, memory):
        doc_id = memory.add_long_term_memory(
            "User loves Python", "preference", 0.9
        )
        results = memory.query_memories("Python", n=1)
        assert "Python" in results[0].get("document", "")

    def test_personality(self, memory):
        tid = memory.add_personality_trait("Playful and kind")
        results = memory.query_personality("kind", n=1)
        assert "kind" in results[0].get("document", "")

    def test_context_rules(self, memory):
        memory.add_context_rule("When VS Code opens", "Code")
        rules = memory.get_context_rules()
        assert "When VS Code opens" in rules[0].get("metadata", {}).get("trigger", "")

    def test_episodic_memory(self, memory):
        doc_id = memory.add_episodic_memory(
            "User completed the project", 0.9, "manual"
        )
        results = memory.query_episodic("project", n=1)
        assert "project" in results[0].get("document", "")
        log = memory.list_episodic_log()
        assert "project" in log[0]["summary"]


class TestSemanticNoteSearch:
    def test_semantic_note_search(self, memory):
        memory.add_note("Python tutorial", "How to use Python for AI development")
        memory.add_note("Shopping list", "Buy milk, eggs, and bread")

        results = memory.search_notes_semantic("programming", n=5)
        assert len(results) > 0
        assert "Python" in results[0].get("metadata", {}).get("title", "")


class TestEdgeCases:
    def test_note_empty_title(self, memory):
        note_id = memory.add_note("", "Some content")
        note = memory.get_note(note_id)
        assert note is not None
        assert note["title"] == ""

    def test_note_empty_content(self, memory):
        note_id = memory.add_note("Title only", "")
        note = memory.get_note(note_id)
        assert note["title"] == "Title only"
        assert note["content"] == ""

    def test_note_empty_both(self, memory):
        note_id = memory.add_note("", "")
        assert memory.get_note(note_id) is not None

    def test_note_special_characters(self, memory):
        note_id = memory.add_note("Special: @#$%", "Content with \n newlines \t tabs")
        note = memory.get_note(note_id)
        assert note["title"] == "Special: @#$%"
        assert "newlines" in note["content"]

    def test_note_very_long_title(self, memory):
        long_title = "A" * 1000
        note_id = memory.add_note(long_title, "content")
        note = memory.get_note(note_id)
        assert len(note["title"]) == 1000

    def test_reminder_no_message(self, memory):
        rem_id = memory.add_reminder("", "2000-01-01 00:00:00")
        due = memory.get_due_reminders()
        assert rem_id in [r["id"] for r in due]

    def test_reminder_special_characters(self, memory):
        rem_id = memory.add_reminder("Remind me: finish project! @home", "2000-01-01 00:00:00")
        due = memory.get_due_reminders()
        assert rem_id in [r["id"] for r in due]

    def test_reminder_empty_trigger_time(self, memory):
        rem_id = memory.add_reminder("Test", "")
        reminders = memory.list_reminders()
        assert rem_id in [r["id"] for r in reminders]

    def test_episodic_memory_empty_summary(self, memory):
        doc_id = memory.add_episodic_memory("", 0.5, "manual")
        logs = memory.list_episodic_log()
        assert any(l["summary"] == "" for l in logs)

    def test_episodic_memory_min_importance(self, memory):
        doc_id = memory.add_episodic_memory("Zero importance", 0.0, "manual")
        logs = memory.list_episodic_log()
        match = [l for l in logs if l["summary"] == "Zero importance"]
        assert match[0]["importance_score"] == 0.0

    def test_episodic_memory_max_importance(self, memory):
        doc_id = memory.add_episodic_memory("Max importance", 1.0, "manual")
        logs = memory.list_episodic_log()
        match = [l for l in logs if l["summary"] == "Max importance"]
        assert match[0]["importance_score"] == 1.0

    def test_delete_nonexistent_note(self, memory):
        memory.delete_note(99999)

    def test_deactivate_nonexistent_reminder(self, memory):
        memory.deactivate_reminder(99999)

    def test_get_nonexistent_preference(self, memory):
        assert memory.get_preference("nonexistent_key") is None

    def test_clear_empty_short_term(self, memory):
        memory.clear_short_term()
        assert memory.get_recent_messages() == []
