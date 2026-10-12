from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QMessageBox


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


def _button_with_text(box, text):
    """Botón del QMessageBox cuya etiqueta es ``text``.

    ``confirm()`` los añade con ``addButton``, así que no se pueden recuperar
    por ``StandardButton``.
    """
    return next(b for b in box.buttons() if b.text() == text)


@pytest.fixture(autouse=True)
def no_blocking_message_box(monkeypatch):
    """Ningún test puede abrir un QMessageBox modal real (colgaría la suite).

    Notas, memorias y recordatorios piden confirmación antes de borrar. Por
    defecto se responde "confirmar" para no cambiar la semántica de los tests
    que ya existían.
    """
    def fake_exec(self):
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: _button_with_text(self, "dialogs.confirm.accept"),
    )


class TestConfirmHelper:
    """``src.gui.utils.confirm`` nunca lanza y solo acepta con "confirmar"."""

    @staticmethod
    def _answer(monkeypatch, answer_key):
        boxes = []

        def fake_exec(self):
            boxes.append(self)
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(
            QMessageBox,
            "clickedButton",
            lambda self: _button_with_text(self, answer_key),
        )
        return boxes

    def test_returns_true_with_the_accept_button(self, mock_i18n, monkeypatch):
        from src.gui.utils import confirm

        self._answer(monkeypatch, "dialogs.confirm.accept")

        assert confirm(
            None, mock_i18n,
            title_key="dialogs.notes.delete_confirm_title",
            body_key="dialogs.notes.delete_confirm_body",
        ) is True

    def test_returns_false_with_the_cancel_button(self, mock_i18n, monkeypatch):
        from src.gui.utils import confirm

        self._answer(monkeypatch, "dialogs.confirm.cancel")

        assert confirm(
            None, mock_i18n,
            title_key="dialogs.notes.delete_confirm_title",
            body_key="dialogs.notes.delete_confirm_body",
        ) is False

    def test_closing_without_answering_is_not_a_confirmation(
        self, mock_i18n, monkeypatch
    ):
        """Esc sobre el diálogo: clickedButton() es None y no se acepta nada."""
        from src.gui.utils import confirm

        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: None)

        assert confirm(
            None, mock_i18n,
            title_key="dialogs.notes.delete_confirm_title",
            body_key="dialogs.notes.delete_confirm_body",
        ) is False

    def test_uses_translated_labels_and_cancel_is_the_default(
        self, mock_i18n, monkeypatch
    ):
        from src.gui.utils import confirm

        boxes = self._answer(monkeypatch, "dialogs.confirm.accept")

        confirm(
            None, mock_i18n,
            title_key="dialogs.memories.delete_confirm_title",
            body_key="dialogs.memories.delete_confirm_body",
            accept_key="dialogs.confirm.accept",
            cancel_key="dialogs.confirm.cancel",
        )

        assert len(boxes) == 1
        box = boxes[0]
        assert box.windowTitle() == "dialogs.memories.delete_confirm_title"
        assert box.text() == "dialogs.memories.delete_confirm_body"
        cancel = _button_with_text(box, "dialogs.confirm.cancel")
        accept = _button_with_text(box, "dialogs.confirm.accept")
        assert box.defaultButton() is cancel
        assert box.defaultButton() is not accept

    def test_custom_button_labels(self, mock_i18n, monkeypatch):
        from src.gui.utils import confirm

        boxes = self._answer(monkeypatch, "dialogs.settings.discard_confirm")

        confirm(
            None, mock_i18n,
            title_key="dialogs.settings.discard_title",
            body_key="dialogs.settings.discard_body",
            accept_key="dialogs.settings.discard_confirm",
            cancel_key="dialogs.settings.discard_cancel",
        )

        assert _button_with_text(boxes[0], "dialogs.settings.discard_confirm")

    def test_returns_false_when_the_box_cannot_be_built(self, mock_i18n):
        """Si el diálogo revienta, la operación destructiva se cancela."""
        from src.gui.utils import confirm

        with patch("src.gui.utils.QMessageBox", side_effect=RuntimeError("boom")):
            assert confirm(
                None, mock_i18n,
                title_key="dialogs.notes.delete_confirm_title",
                body_key="dialogs.notes.delete_confirm_body",
            ) is False

    def test_returns_false_when_exec_raises(self, mock_i18n, monkeypatch):
        from src.gui.utils import confirm

        def boom(self):
            raise RuntimeError("sin display")

        monkeypatch.setattr(QMessageBox, "exec", boom)

        assert confirm(
            None, mock_i18n,
            title_key="dialogs.reminders.cancel_confirm_title",
            body_key="dialogs.reminders.cancel_confirm_body",
        ) is False

    def test_broken_i18n_shows_the_raw_key_instead_of_raising(self, monkeypatch):
        """Sin traducciones el botón se ve con la clave, pero sigue funcionando."""
        from src.gui.utils import confirm

        boxes = self._answer(monkeypatch, "dialogs.confirm.accept")
        broken = MagicMock()
        broken.t.side_effect = KeyError("sin locale")

        assert confirm(
            None, broken,
            title_key="dialogs.notes.unsaved_title",
            body_key="dialogs.notes.unsaved_body",
        ) is True

        assert boxes[0].windowTitle() == "dialogs.notes.unsaved_title"

    def test_without_i18n_object_does_not_raise(self, monkeypatch):
        from src.gui.utils import confirm

        self._answer(monkeypatch, "dialogs.confirm.accept")

        assert confirm(
            None, None,
            title_key="dialogs.notes.delete_confirm_title",
            body_key="dialogs.notes.delete_confirm_body",
        ) is True


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

    @staticmethod
    def _first_bubble(widget):
        """Devuelve la primera MessageBubble del chat (o None)."""
        from src.gui.widgets.chat_widget import MessageBubble
        item = widget.message_layout.itemAt(0)
        row = item.widget() if item else None
        if row is None or row.layout() is None:
            return None
        for j in range(row.layout().count()):
            child = row.layout().itemAt(j).widget()
            if isinstance(child, MessageBubble):
                return child
        return None

    def test_autoscroll_follows_new_messages(self, qtbot, mock_i18n):
        """El chat debe quedarse pegado al fondo al desbordarse el área."""
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        widget.resize(420, 320)
        qtbot.addWidget(widget)
        widget.show()

        for i in range(30):
            widget.add_message(
                "user",
                f"Mensaje {i} con texto suficiente para ocupar varias lineas",
            )

        # El rango solo se recalcula cuando el layout procesa el LayoutRequest.
        sb = widget.scroll_area.verticalScrollBar()
        qtbot.waitUntil(lambda: sb.maximum() > 0, timeout=2000)
        qtbot.wait(100)  # deja correr el QTimer.singleShot(0) del autoscroll

        assert sb.maximum() > 0, "el historial debería desbordar el viewport"
        assert sb.value() == sb.maximum()

    def test_no_autoscroll_when_user_scrolled_up(self, qtbot, mock_i18n):
        """Si el usuario lee más arriba, un mensaje nuevo no le arrastra."""
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        widget.resize(420, 320)
        qtbot.addWidget(widget)
        widget.show()

        for i in range(30):
            widget.add_message("assistant", f"Respuesta {i} bastante larga de verdad")

        sb = widget.scroll_area.verticalScrollBar()
        qtbot.waitUntil(lambda: sb.maximum() > 0, timeout=2000)
        qtbot.wait(100)
        assert sb.maximum() > 0

        max_before = sb.maximum()
        sb.setValue(0)

        widget.add_message("assistant", "Un mensaje nuevo que no debe arrastrar la vista")
        qtbot.waitUntil(lambda: sb.maximum() > max_before, timeout=2000)
        qtbot.wait(100)

        assert sb.value() <= 4

    def test_bubble_text_is_selectable(self, qtbot, mock_i18n):
        """Sin flags de selección no hay menú contextual ni copiado."""
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        qtbot.addWidget(widget)
        widget.add_message("assistant", "Texto que se debe poder copiar")

        bubble = self._first_bubble(widget)
        assert bubble is not None
        flags = bubble.label.textInteractionFlags()
        assert flags & Qt.TextSelectableByMouse
        assert bubble.label.accessibleName() == "assistant"
        assert bubble.label.accessibleDescription() == "Texto que se debe poder copiar"

    def test_system_bubble_uses_small_font(self, qtbot, mock_i18n):
        """Design.md §1.2/§2.3: los avisos de sistema van a 11px."""
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n)
        qtbot.addWidget(widget)
        widget.add_message("system", "Aviso del sistema")

        bubble = self._first_bubble(widget)
        assert bubble is not None
        label_qss = bubble.label.styleSheet()
        assert "font-size: 11px" in label_qss
        assert "font-size: 13px" not in label_qss
        assert '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif' in label_qss

    def test_bubble_sheets_come_from_styles(self, qtbot, mock_i18n):
        """La burbuja pide su QSS al sistema de diseño, no lo construye."""
        from src.gui.styles import styles as s
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n, theme="dark")
        qtbot.addWidget(widget)
        widget.add_message("assistant", "Hola")

        bubble = self._first_bubble(widget)
        assert bubble.styleSheet() == s.chat_bubble_frame_qss("assistant", "dark")
        assert bubble.label.styleSheet() == s.chat_bubble_label_qss("assistant", "dark")
        assert widget.styleSheet() == s.chat_frame_qss("dark")

    def test_set_theme_reapplies_styles(self, qtbot, mock_i18n):
        """Cambiar de tema debe repintar el marco y todas las burbujas."""
        from src.gui.styles import styles as s
        from src.gui.widgets.chat_widget import ChatWidget
        widget = ChatWidget(i18n=mock_i18n, theme="light")
        qtbot.addWidget(widget)
        widget.add_message("assistant", "Hola")

        widget.set_theme("dark")

        assert widget.styleSheet() == s.chat_frame_qss("dark")
        bubble = self._first_bubble(widget)
        assert s.BG_SURFACE_DK in bubble.styleSheet()
        assert s.BORDER_DK in bubble.styleSheet()
        assert s.TEXT_PRIMARY_DK in bubble.label.styleSheet()


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


class TestForceTaskbarEntryHelper:
    @staticmethod
    def _make_dialog(qtbot):
        from PySide6.QtWidgets import QDialog

        dialog = QDialog()
        qtbot.addWidget(dialog)
        return dialog

    def test_delegates_to_platform_adapter_with_hwnd(self, qtbot):
        from src.gui.utils import force_taskbar_entry

        dialog = self._make_dialog(qtbot)
        adapter = MagicMock()
        adapter.capabilities.taskbar_entry = True
        adapter.force_taskbar_entry.return_value = True
        with patch("src.gui.utils.get_platform", return_value=adapter):
            result = force_taskbar_entry(dialog)
        assert result is True
        adapter.force_taskbar_entry.assert_called_once()
        hwnd = adapter.force_taskbar_entry.call_args[0][0]
        assert isinstance(hwnd, int)
        assert hwnd == int(dialog.winId())

    def test_noop_when_taskbar_entry_unsupported(self, qtbot):
        from src.gui.utils import force_taskbar_entry

        dialog = self._make_dialog(qtbot)
        adapter = MagicMock()
        adapter.capabilities.taskbar_entry = False
        with patch("src.gui.utils.get_platform", return_value=adapter):
            result = force_taskbar_entry(dialog)
        assert result is False
        adapter.force_taskbar_entry.assert_not_called()


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

    def test_apply_character_name_updates_title_and_menu(
        self, qtbot, mock_memory_manager, mock_config, mock_i18n
    ):
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window._apply_character_name("Lin")
        assert window.windowTitle() == "app.title"
        assert window._char_menu.title() == "Lin"
        assert mock_config["personality"]["name"] == "Lin"

    @patch("PySide6.QtWidgets.QMessageBox.about")
    def test_about_dialog(self, mock_about, qtbot, mock_memory_manager, mock_config, mock_i18n):
        from src import __version__
        from src.gui.windows.main_window import MainWindow
        window = MainWindow(config=mock_config, memory_manager=mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(window)
        window._show_about()
        mock_about.assert_called_once()
        body = mock_about.call_args[0][2]
        assert f"TomoDesk v{__version__}" in body
        assert "v0.1.0" not in body

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
