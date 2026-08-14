from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer


@pytest.fixture
def mock_config():
    return {
        "personality": {"name": "Tomo"},
        "llm": {"model": "llama3.2:1b", "endpoint": "http://localhost:11434"},
        "modes": {},
    }


@pytest.fixture
def mock_memory_manager():
    return MagicMock()


@pytest.fixture(autouse=True)
def ensure_qapp(qapp):
    return qapp


class TestChatWidget:
    def test_add_message_user(self, qtbot, mock_i18n):
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        qtbot.addWidget(widget)
        widget.add_message("user", "Hello")
        assert "Hello" in widget.toPlainText()

    def test_add_message_assistant(self, qtbot, mock_i18n):
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        qtbot.addWidget(widget)
        widget.add_message("assistant", "Hi there")
        assert "Hi there" in widget.toPlainText()

    def test_add_message_system(self, qtbot, mock_i18n):
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        qtbot.addWidget(widget)
        widget.add_message("system", "System message")
        assert "System message" in widget.toPlainText()


class TestNotesDialog:
    def test_open_and_close(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_notes.return_value = []
        from src.gui.windows.notes_dialog import NotesDialog
        dialog = NotesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.show()
        assert dialog.isVisible()

    def test_save_note(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_notes.return_value = []
        mock_memory_manager.add_note.return_value = 1
        from src.gui.windows.notes_dialog import NotesDialog
        dialog = NotesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.title_input.setText("Test Title")
        dialog.content_input.setPlainText("Test Content")
        dialog._save_note()
        mock_memory_manager.add_note.assert_called_once_with("Test Title", "Test Content")

    def test_delete_note(self, qtbot, mock_memory_manager, mock_i18n):
        mock_note = {"id": 1, "title": "Test", "content": "content"}
        mock_memory_manager.list_notes.return_value = [mock_note]
        from src.gui.windows.notes_dialog import NotesDialog
        dialog = NotesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.note_list.setCurrentRow(0)
        dialog._delete_note()
        mock_memory_manager.delete_note.assert_called_once_with(1)


class TestRemindersDialog:
    def test_open_and_close(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_reminders.return_value = []
        from src.gui.windows.reminders_dialog import RemindersDialog
        dialog = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.show()
        assert dialog.isVisible()

    def test_add_reminder(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_reminders.return_value = []
        mock_memory_manager.add_reminder.return_value = 1
        from src.gui.windows.reminders_dialog import RemindersDialog
        dialog = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.message_input.setText("Test reminder")
        dialog._add_reminder()
        assert mock_memory_manager.add_reminder.called

    def test_cancel_reminder(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_reminders.return_value = [
            {"id": 1, "message": "Test", "trigger_time": "2025-01-01 12:00"}
        ]
        from src.gui.windows.reminders_dialog import RemindersDialog
        dialog = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.reminder_list.setCurrentRow(0)
        dialog._cancel_reminder()
        mock_memory_manager.deactivate_reminder.assert_called_once_with(1)


class TestMemoriesDialog:
    def test_open_and_close(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_episodic_log.return_value = []
        from src.gui.windows.memories_dialog import MemoriesDialog
        dialog = MemoriesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.show()
        assert dialog.isVisible()

    def test_delete_memory(self, qtbot, mock_memory_manager, mock_i18n):
        mock_memory_manager.list_episodic_log.return_value = [
            {"id": 1, "summary": "Test", "source": "manual", "importance_score": 0.8}
        ]
        from src.gui.windows.memories_dialog import MemoriesDialog
        dialog = MemoriesDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(dialog)
        dialog.memory_list.setCurrentRow(0)
        dialog._delete_memory()
        mock_memory_manager.delete_episodic_memory.assert_called_once_with(1)


class TestMainWindow:
    def test_create_window(self, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window.show()
        assert window.isVisible()
        assert "app.title" in window.windowTitle()

    def test_send_user_message(self, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window.input.setText("Hello")
        window._send_message()
        assert "Hello" in window.chat.toPlainText()

    def test_send_command_no_notes(self, qtbot, mock_memory_manager, mock_config, mock_i18n):
        mock_memory_manager.list_notes.return_value = []
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window.input.setText("/note list")
        window._send_message()
        assert "commands.no_notes_found" in window.chat.toPlainText()

    def test_status_bar_update(self, qtbot, mock_memory_manager, mock_config, mock_i18n, mock_state_manager):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(
            config=mock_config, memory_manager=mock_memory_manager,
            i18n=mock_i18n, state_manager=mock_state_manager,
        )
        qtbot.addWidget(window)
        window._update_status_message()
        assert window.mood_label.text() != ""

    @patch("PySide6.QtWidgets.QMessageBox.about")
    def test_about_dialog(self, mock_about, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window._show_about()
        mock_about.assert_called_once()

    @patch("PySide6.QtWidgets.QDialog.exec", return_value=0)
    def test_open_notes_dialog(self, mock_exec, qtbot, mock_memory_manager, mock_config, mock_i18n):
        mock_memory_manager.list_notes.return_value = []
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window.open_notes()
        mock_exec.assert_called_once()

    @patch("PySide6.QtWidgets.QDialog.exec", return_value=0)
    def test_open_reminders_dialog(self, mock_exec, qtbot, mock_memory_manager, mock_config, mock_i18n):
        mock_memory_manager.list_reminders.return_value = []
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window.open_reminders()
        mock_exec.assert_called_once()

    @patch("PySide6.QtWidgets.QDialog.exec", return_value=0)
    def test_open_memories_dialog(self, mock_exec, qtbot, mock_memory_manager, mock_config, mock_i18n):
        mock_memory_manager.list_episodic_log.return_value = []
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window._open_memories()
        mock_exec.assert_called_once()

    @patch("PySide6.QtWidgets.QDialog.show")
    def test_open_settings_dialog(self, mock_show, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window._open_settings()
        mock_show.assert_called_once()

    def test_input_placeholder(self, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        assert len(window.input.placeholderText()) > 0
