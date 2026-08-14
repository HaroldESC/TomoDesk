from src.memory.episodic_utils import detect_milestone_keywords, suggest_memory_from_conversation


def test_detect_milestone_keywords():
    messages = [
        {"role": "user", "content": "Terminé el proyecto TomoDesk"},
        {"role": "user", "content": "Hoy aprendí Python"},
        {"role": "user", "content": "No sé qué comer"},
    ]
    milestones = detect_milestone_keywords(messages)
    assert len(milestones) >= 2
    assert any("Terminé" in m for m in milestones)
    assert any("aprendí" in m for m in milestones)


def test_detect_no_milestones():
    messages = [
        {"role": "user", "content": "Hola"},
        {"role": "user", "content": "Qué tal"},
    ]
    milestones = detect_milestone_keywords(messages)
    assert len(milestones) == 0


def test_suggest_memory_triggers(memory_manager):
    for i in range(4):
        memory_manager.add_message("user", f"Message {i}")
        memory_manager.add_message("assistant", f"Response {i}")

    suggestion = suggest_memory_from_conversation(memory_manager, message_count_threshold=4)
    assert suggestion is not None
    assert "/remember" in suggestion


def test_suggest_memory_no_trigger_short(memory_manager):
    suggestion = suggest_memory_from_conversation(memory_manager, message_count_threshold=15)
    assert suggestion is None


class TestHasRecentSuggestion:
    def test_no_suggestion_returns_false(self, memory_manager):
        assert memory_manager.has_recent_suggestion() is False

    def test_recent_suggestion_returns_true(self, memory_manager):
        memory_manager.add_episodic_log("Test suggestion", 0.5, "suggestion", chroma_id=None)
        assert memory_manager.has_recent_suggestion() is True

    def test_non_suggestion_source_ignored(self, memory_manager):
        memory_manager.add_episodic_log("Auto memory", 0.7, "auto", chroma_id=None)
        assert memory_manager.has_recent_suggestion() is False

    def test_custom_hours_window(self, memory_manager):
        memory_manager.add_episodic_log("Old suggestion", 0.5, "suggestion", chroma_id=None)
        assert memory_manager.has_recent_suggestion(hours=24) is True

    def test_multiple_suggestions(self, memory_manager):
        for i in range(3):
            memory_manager.add_episodic_log(f"Suggestion {i}", 0.5, "suggestion", chroma_id=None)
        assert memory_manager.has_recent_suggestion() is True

    def test_suggest_returns_none_when_recent_suggestion_exists(self, memory_manager):
        memory_manager.add_episodic_log("Recent suggestion", 0.5, "suggestion", chroma_id=None)
        for i in range(4):
            memory_manager.add_message("user", f"Message {i}")
            memory_manager.add_message("assistant", f"Response {i}")
        suggestion = suggest_memory_from_conversation(memory_manager, message_count_threshold=4)
        assert suggestion is None
