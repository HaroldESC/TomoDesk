"""Diálogo de Recordatorios: alta por teclado, cancelación confirmada y vacío.

Cubre la jerarquía de botones (Design.md §2.1) y la Ola 1 de la Fase 3.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton


@pytest.fixture(autouse=True)
def ensure_qapp(qapp):
    return qapp


@pytest.fixture
def mock_memory_manager():
    from unittest.mock import MagicMock

    return MagicMock()


def _button_with_text(box, text):
    """Botón del QMessageBox con esa etiqueta (``addButton``, no StandardButton)."""
    return next(b for b in box.buttons() if b.text() == text)


@pytest.fixture(autouse=True)
def no_blocking_message_box(monkeypatch):
    """Ningun test puede abrir un QMessageBox modal real: la suite se colgaria."""
    def fake_exec(self):
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: _button_with_text(self, "dialogs.confirm.accept"),
    )


@pytest.fixture
def answer(monkeypatch):
    """Fuerza la respuesta del dialogo de confirmacion y captura los boxes."""
    def _answer(accept: bool) -> list:
        key = "dialogs.confirm.accept" if accept else "dialogs.confirm.cancel"
        boxes = []

        def fake_exec(self):
            boxes.append(self)
            return 0

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        monkeypatch.setattr(
            QMessageBox,
            "clickedButton",
            lambda self: _button_with_text(self, key),
        )
        return boxes

    return _answer


def _reminder(reminder_id: int = 1, **overrides) -> dict:
    data = {
        "id": reminder_id,
        "message": "llamar al dentista",
        "trigger_time": "2026-03-04 05:06:07",
    }
    data.update(overrides)
    return data


@pytest.fixture
def dialog(qtbot, mock_memory_manager, mock_i18n):
    mock_memory_manager.list_reminders.return_value = []
    from src.gui.windows.reminders_dialog import RemindersDialog

    widget = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def make_dialog(qtbot, mock_memory_manager, mock_i18n):
    """Construye el diálogo con una lista de recordatorios concreta."""
    def _make(reminders) -> object:
        mock_memory_manager.list_reminders.return_value = reminders
        from src.gui.windows.reminders_dialog import RemindersDialog

        widget = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
        qtbot.addWidget(widget)
        return widget

    return _make


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


def _label_with_text(dialog, text):
    """``QLabel`` del diálogo cuyo texto coincide (mock_i18n devuelve la clave)."""
    return next(
        label for label in dialog.findChildren(QLabel) if label.text() == text
    )


def _tab_sequence(dialog, steps):
    """Widgets que reciben el foco al pulsar Tab ``steps`` veces seguidas."""
    qapp = QApplication.instance()
    widgets = [dialog.focusWidget()]
    for _ in range(steps):
        QTest.keyClick(widgets[-1], Qt.Key.Key_Tab)
        qapp.processEvents()
        widgets.append(dialog.focusWidget())
    return widgets


class TestButtonHierarchy:
    """``Design.md`` §2.1: un objectName por rol."""

    def test_add_is_the_only_primary(self, dialog):
        roles = _buttons(dialog)
        assert roles["dialogs.reminders.add"] == ""
        assert roles["dialogs.reminders.cancel_selected"] == "danger"
        assert set(roles.values()) <= {"", "danger"}

    def test_every_button_uses_a_known_variant(self, dialog):
        assert set(_buttons(dialog).values()) <= {"", "danger"}


class TestAddWithKeyboard:
    """Escribir el recordatorio y pulsar Enter debe bastar."""

    def test_return_pressed_adds_the_reminder(self, dialog, mock_memory_manager):
        dialog.message_input.setText("comprar pan")
        dialog.minutes_spin.setValue(15)

        dialog.message_input.returnPressed.emit()

        assert mock_memory_manager.add_reminder.call_count == 1
        message, trigger_time = mock_memory_manager.add_reminder.call_args[0]
        assert message == "comprar pan"
        assert len(trigger_time) == 19  # "%Y-%m-%d %H:%M:%S"

    def test_return_pressed_clears_the_input_and_refreshes(
        self, dialog, mock_memory_manager
    ):
        dialog.message_input.setText("comprar pan")

        dialog.message_input.returnPressed.emit()

        assert dialog.message_input.text() == ""
        assert mock_memory_manager.list_reminders.call_count == 2

    def test_empty_message_does_nothing(self, dialog, mock_memory_manager):
        dialog.message_input.setText("   ")

        dialog.message_input.returnPressed.emit()

        mock_memory_manager.add_reminder.assert_not_called()


class TestCancelConfirmation:
    """Cancelar desactiva el recordatorio: se pregunta antes."""

    def test_declining_keeps_the_reminder(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_reminder()])
        answer(False)
        dialog.reminder_list.setCurrentRow(0)

        dialog._cancel_reminder()

        mock_memory_manager.deactivate_reminder.assert_not_called()
        assert dialog.reminder_list.count() == 1

    def test_accepting_deactivates_and_refreshes(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_reminder()])
        answer(True)
        dialog.reminder_list.setCurrentRow(0)

        dialog._cancel_reminder()

        mock_memory_manager.deactivate_reminder.assert_called_once_with(1)
        assert mock_memory_manager.list_reminders.call_count == 2

    def test_prompt_uses_the_reminder_keys(self, make_dialog, answer):
        dialog = make_dialog([_reminder()])
        boxes = answer(False)
        dialog.reminder_list.setCurrentRow(0)

        dialog._cancel_reminder()

        assert len(boxes) == 1
        assert boxes[0].windowTitle() == "dialogs.reminders.cancel_confirm_title"
        assert boxes[0].text() == "dialogs.reminders.cancel_confirm_body"

    def test_without_selection_nothing_happens(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_reminder()])
        answer(True)

        dialog._cancel_reminder()

        mock_memory_manager.deactivate_reminder.assert_not_called()

    def test_button_click_goes_through_the_confirmation(
        self, qtbot, make_dialog, mock_memory_manager, answer
    ):
        from PySide6.QtCore import Qt

        dialog = make_dialog([_reminder()])
        answer(False)
        dialog.reminder_list.setCurrentRow(0)

        qtbot.mouseClick(dialog.cancel_btn, Qt.MouseButton.LeftButton)

        mock_memory_manager.deactivate_reminder.assert_not_called()


class TestCancelActionState:
    """Cancelar sigue la selección en vez de fallar en silencio (bug manual)."""

    def test_cancel_is_disabled_without_selection(self, make_dialog):
        dialog = make_dialog([_reminder()])

        assert dialog.cancel_btn.isEnabled() is False

    def test_cancel_enables_when_a_reminder_is_selected(self, make_dialog):
        dialog = make_dialog([_reminder()])

        dialog.reminder_list.setCurrentRow(0)

        assert dialog.cancel_btn.isEnabled() is True

    def test_cancel_disables_when_the_selection_is_cleared(self, make_dialog):
        dialog = make_dialog([_reminder()])
        dialog.reminder_list.setCurrentRow(0)

        dialog.reminder_list.setCurrentRow(-1)

        assert dialog.cancel_btn.isEnabled() is False

    def test_cancel_disables_again_after_cancelling(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_reminder()])
        answer(True)
        mock_memory_manager.list_reminders.return_value = []
        dialog.reminder_list.setCurrentRow(0)

        dialog._cancel_reminder()

        assert dialog.cancel_btn.isEnabled() is False

    def test_tooltip_is_set(self, make_dialog):
        dialog = make_dialog([_reminder()])

        assert dialog.cancel_btn.toolTip() == "dialogs.reminders.cancel_tip"

    def test_clicking_cancel_without_selection_does_not_deactivate(
        self, make_dialog, mock_memory_manager, answer
    ):
        """Regresión: el botón deshabilitado no llega a ``_cancel_reminder``."""
        dialog = make_dialog([_reminder()])
        answer(True)

        dialog.cancel_btn.click()

        mock_memory_manager.deactivate_reminder.assert_not_called()


class TestListRobustness:
    """``trigger_time`` no siempre viene con la forma esperada."""

    def test_trigger_time_is_shown_without_seconds(self, make_dialog):
        dialog = make_dialog([_reminder()])

        assert _reminder_item_kwargs(dialog)["time"] == "2026-03-04 05:06"

    def test_short_trigger_time_is_not_padded(self, make_dialog):
        dialog = make_dialog([_reminder(trigger_time="2026-03-04")])

        assert _reminder_item_kwargs(dialog)["time"] == "2026-03-04"

    @pytest.mark.parametrize("value", [None, "", 12345])
    def test_missing_trigger_time_does_not_raise(self, make_dialog, value):
        dialog = make_dialog([_reminder(trigger_time=value)])

        assert _reminder_item_kwargs(dialog)["time"] == ""

    def test_long_message_is_truncated_but_kept_in_the_tooltip(self, make_dialog):
        message = "L" * 120
        dialog = make_dialog([_reminder(message=message)])

        assert _reminder_item_kwargs(dialog)["message"] == "L" * 50
        assert dialog.reminder_list.item(0).toolTip() == message


class TestEmptyList:
    """Sin recordatorios la lista no es un hueco mudo."""

    def test_empty_list_shows_the_empty_label(self, dialog):
        assert dialog.empty_label.text() == "dialogs.reminders.empty"
        assert dialog.empty_label.isVisibleTo(dialog) is True
        assert dialog.reminder_list.isVisibleTo(dialog) is False

    def test_non_empty_list_hides_the_empty_label(self, make_dialog):
        dialog = make_dialog([_reminder()])

        assert dialog.empty_label.isVisibleTo(dialog) is False
        assert dialog.reminder_list.isVisibleTo(dialog) is True

    def test_cancelling_the_last_reminder_shows_the_empty_state(
        self, make_dialog, mock_memory_manager, answer
    ):
        dialog = make_dialog([_reminder()])
        answer(True)
        mock_memory_manager.list_reminders.return_value = []
        dialog.reminder_list.setCurrentRow(0)

        dialog._cancel_reminder()

        assert dialog.empty_label.isVisibleTo(dialog) is True


def _reminder_item_kwargs(dialog) -> dict:
    """Argumentos de la última llamada a ``i18n.t`` de tipo ``reminder_item``."""
    for call in reversed(dialog.i18n.t.call_args_list):
        if call.args and call.args[0] == "commands.reminder_item":
            return call.kwargs
    raise AssertionError("no se pidio ninguna etiqueta commands.reminder_item")


class TestTabOrder:
    """Ola 3 B6.2: el recorrido de Tab sigue el orden documentado."""

    def test_tab_visits_widgets_in_order(self, make_dialog, qapp):
        dialog = make_dialog([_reminder()])
        dialog.show()
        qapp.processEvents()
        dialog.reminder_list.setFocus()
        qapp.processEvents()

        assert _tab_sequence(dialog, 4) == [
            dialog.reminder_list,
            dialog.message_input,
            dialog.minutes_spin,
            dialog.add_btn,
            dialog.cancel_btn,
        ]


class TestAccessibility:
    """Ola 3 B6.3: etiquetas clicables y nombres accesibles."""

    def test_active_reminders_label_points_at_the_list(self, dialog):
        label = _label_with_text(dialog, "dialogs.reminders.active_reminders")
        assert label.buddy() is dialog.reminder_list

    def test_new_reminder_label_points_at_the_input(self, dialog):
        label = _label_with_text(dialog, "dialogs.reminders.new_reminder")
        assert label.buddy() is dialog.message_input

    def test_minutes_label_points_at_the_spinbox(self, dialog):
        label = _label_with_text(dialog, "dialogs.reminders.minutes_from_now")
        assert label.buddy() is dialog.minutes_spin

    def test_list_exposes_an_accessible_name(self, dialog):
        assert (
            dialog.reminder_list.accessibleName()
            == "dialogs.reminders.active_reminders"
        )
