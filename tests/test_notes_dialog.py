"""Jerarquía de botones del diálogo de Notas (Design.md §2.1)."""

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
    mock_memory_manager.list_notes.return_value = []
    from src.gui.windows.notes_dialog import NotesDialog

    widget = NotesDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


def test_save_is_the_only_primary(dialog):
    """Guardar no lleva objectName; el resto usa una variante conocida."""
    roles = _buttons(dialog)
    assert roles["dialogs.notes.save"] == ""
    assert roles["dialogs.notes.delete"] == "danger"
    assert roles["dialogs.notes.new"] == "secondary"
    assert set(roles.values()) <= {"", "danger", "secondary"}


def test_delete_is_destructive_and_new_is_secondary(dialog):
    roles = _buttons(dialog)
    assert roles["dialogs.notes.delete"] == "danger"
    assert roles["dialogs.notes.new"] == "secondary"
