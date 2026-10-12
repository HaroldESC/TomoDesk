"""Jerarquía de botones del diálogo de Memorias (Design.md §2.1)."""

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
    mock_memory_manager.list_episodic_log.return_value = []
    from src.gui.windows.memories_dialog import MemoriesDialog

    widget = MemoriesDialog(mock_memory_manager, i18n=mock_i18n)
    qtbot.addWidget(widget)
    return widget


def _buttons(dialog):
    return {b.text(): b.objectName() for b in dialog.findChildren(QPushButton)}


def test_delete_is_danger_and_refresh_is_flat(dialog):
    roles = _buttons(dialog)
    assert roles["dialogs.memories.delete"] == "danger"
    assert roles["dialogs.memories.refresh"] == "flat"
    # No hay accion primaria en este dialogo: solo utilidad y destruccion.
    assert set(roles.values()) == {"danger", "flat"}
