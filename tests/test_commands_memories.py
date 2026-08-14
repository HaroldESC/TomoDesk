from src.system.commands import cmd_memories, cmd_remember


def test_remember_with_importance(memory_manager, mock_i18n):
    msg, continue_loop = cmd_remember("importance:9 Finished prototype", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_preview" in msg


def test_remember_without_importance(memory_manager, mock_i18n):
    msg, continue_loop = cmd_remember("Just a normal memory", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_preview" in msg


def test_remember_empty(memory_manager, mock_i18n):
    msg, continue_loop = cmd_remember("", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remember_usage" in msg


def test_memories_list(memory_manager, mock_i18n):
    memory_manager.add_episodic_memory("Memory one", 0.5, "manual")
    memory_manager.add_episodic_memory("Memory two", 0.8, "manual")

    msg, continue_loop = cmd_memories("list", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_item" in msg


def test_memories_search(memory_manager, mock_i18n):
    memory_manager.add_episodic_memory("Started learning guitar", 0.7, "manual")
    memory_manager.add_episodic_memory("Finished reading Dune", 0.6, "manual")

    msg, continue_loop = cmd_memories("search music", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memories_matching_header" in msg


def test_memories_important(memory_manager, mock_i18n):
    memory_manager.add_episodic_memory("Low importance", 0.3, "manual")
    memory_manager.add_episodic_memory("High importance", 0.9, "manual")

    msg, continue_loop = cmd_memories("important", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_important_item" in msg
    assert "commands.no_important_memories" not in msg


def test_memories_delete(memory_manager, mock_i18n):
    memory_manager.add_episodic_memory("Delete me", 0.5, "manual")
    logs = memory_manager.list_episodic_log()
    log_id = logs[0]["id"]

    msg, continue_loop = cmd_memories(f"delete {log_id}", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "deleted" in msg.lower()

    logs = memory_manager.list_episodic_log()
    assert len(logs) == 0
