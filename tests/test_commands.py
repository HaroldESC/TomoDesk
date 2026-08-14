import pytest

from src.system.commands import (
    cmd_exit,
    cmd_help,
    cmd_note_add,
    cmd_note_list,
    handle_command,
)


def test_cmd_exit():
    msg, continue_loop = handle_command("/exit", None, {})
    assert continue_loop is False


def test_cmd_help(mock_i18n):
    msg, continue_loop = handle_command("/help", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.help_text" in msg


def test_note_add_and_list(memory_manager, mock_i18n):
    msg, continue_loop = cmd_note_add("Test Title | Test Content", memory_manager, i18n=mock_i18n)
    assert continue_loop is True
    assert "saved" in msg.lower()

    msg, continue_loop = cmd_note_list(memory_manager, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_list_item" in msg


def test_note_add_no_title(memory_manager, mock_i18n):
    msg, continue_loop = cmd_note_add("", memory_manager, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_title_empty" in msg


def test_note_show_and_delete(memory_manager, mock_i18n):
    cmd_note_add("Delete Me | Content", memory_manager, i18n=mock_i18n)
    msg, continue_loop = handle_command("/note show 1", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_detail_title" in msg

    msg, continue_loop = handle_command("/note delete 1", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_delete_confirm" in msg


def test_remind_add_and_list(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind in 10 Buy milk", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.reminder_set_msg" in msg

    msg, continue_loop = handle_command("/remind list", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.reminder_item" in msg


def test_remember_and_memories(memory_manager, mock_i18n):
    msg, continue_loop = handle_command(
        "/remember Started project TomoDesk", memory_manager, {}, i18n=mock_i18n
    )
    assert continue_loop is True
    assert "commands.memory_preview" in msg

    msg, continue_loop = handle_command("/memories", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_item" in msg


def test_clear(memory_manager, mock_i18n):
    memory_manager.add_message("user", "Hello")
    assert len(memory_manager.get_recent_messages()) == 1

    msg, continue_loop = handle_command("/clear", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert len(memory_manager.get_recent_messages()) == 0


def test_unknown_command(mock_i18n):
    msg, continue_loop = handle_command("/unknown", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.unknown_command" in msg


def test_note_delete_negative_id(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note delete -1", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_not_found" in msg


def test_note_delete_non_numeric(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note delete abc", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_delete_usage" in msg


def test_note_show_nonexistent(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note show 99999", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_not_found" in msg


def test_note_show_non_numeric(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note show abc", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_show_usage" in msg


def test_note_search_empty(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note search", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_search_usage" in msg


def test_remind_invalid_syntax(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind xyz", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remind_unknown_subcmd" in msg


def test_remind_invalid_minutes(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind in abc Buy milk", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remind_minutes_number" in msg


def test_remind_missing_message(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind in 5", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remind_add_usage" in msg


def test_remind_cancel_non_numeric(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind cancel abc", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remind_cancel_usage" in msg


def test_remember_importance_invalid(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remember importance:abc", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remember_invalid_importance" in msg


def test_remember_importance_no_text(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remember importance:8", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remember_text_empty" in msg


def test_remember_empty(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remember", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remember_usage" in msg


def test_memories_delete_non_numeric(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/memories delete abc", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memories_delete_usage" in msg


def test_memories_delete_nonexistent(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/memories delete 99999", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memory_not_found" in msg


def test_memories_search_empty(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/memories search", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.memories_search_usage" in msg


def test_note_unknown_subcommand(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/note wat", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.note_unknown_subcmd" in msg


def test_remind_no_subcommand(memory_manager, mock_i18n):
    msg, continue_loop = handle_command("/remind", memory_manager, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.remind_usage" in msg
