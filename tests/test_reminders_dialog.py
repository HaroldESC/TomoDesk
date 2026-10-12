"""Jerarquía de botones del diálogo de Recordatorios (Design.md §2.1)."""

import pytest
from PySide6.QtWidgets import QPushButton


@pytest.fixture(autouse=True)
def ensure_qapp(qapp):
    return qapp


@pytest.fixture
def mock_memory_manager():
    from unittest.mock import MagicMock

    return MagicMock()


@pytest.fixture
def dialog(qtbot, mock_memory_manager, mock_i18n):
    mock_memory_manager.list_reminders.return_value = []
    from src.gui.windows.reminders_dialog import RemindersDialog

    widget = RemindersDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


def test_add_is_the_only_primary(dialog):
    roles = _buttons(dialog)
    assert roles["dialogs.reminders.add"] == ""
    assert roles["dialogs.reminders.cancel_selected"] == "danger"
    assert set(roles.values()) <= {"", "danger"}
