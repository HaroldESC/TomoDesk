from src.system.commands import cmd_episodic_stats


def test_episodic_stats_empty(memory_manager, mock_i18n):
    msg, continue_loop = cmd_episodic_stats("", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.episodic_empty" in msg


def test_episodic_stats_with_data(memory_manager, mock_i18n):
    memory_manager.add_episodic_memory("Manual memory", 0.8, "manual")
    memory_manager.add_episodic_memory("Auto memory", 0.6, "auto")
    memory_manager.add_episodic_memory("High importance", 0.9, "auto")

    msg, continue_loop = cmd_episodic_stats("", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.episodic_total" in msg
    assert "commands.episodic_manual_auto" in msg
    assert "commands.episodic_avg_importance" in msg
    assert "High importance" in msg
