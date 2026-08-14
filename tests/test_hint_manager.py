import json

import pytest

from src.gui.managers.hint_manager import HintManager


def test_hint_manager_initialization(memory_manager, mock_i18n):
    config = {"ui": {"hints": {"enabled": True}}}
    hm = HintManager(memory_manager, mock_i18n, config)
    assert hm.enabled is True
    assert hm._shown_hints == set()


def test_hint_persistence(memory_manager, mock_i18n):
    config = {"ui": {"hints": {"enabled": True}}}
    hm = HintManager(memory_manager, mock_i18n, config)
    hm.mark_hint_shown("drag")
    hm.mark_hint_shown("click")
    hm2 = HintManager(memory_manager, mock_i18n, config)
    assert hm2.is_hint_shown("drag") is True
    assert hm2.is_hint_shown("click") is True
    assert hm2.is_hint_shown("double_click") is False


def test_hint_disabled(memory_manager, mock_i18n):
    config = {"ui": {"hints": {"enabled": False}}}
    hm = HintManager(memory_manager, mock_i18n, config)
    assert hm.enabled is False
    hm.mark_hint_shown("drag")
    hm2 = HintManager(memory_manager, mock_i18n, config)
    assert hm2.is_hint_shown("drag") is False


def test_show_tooltip(memory_manager, mock_i18n, mocker):
    from PySide6.QtWidgets import QWidget, QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    mock_show = mocker.patch("PySide6.QtWidgets.QToolTip.showText")
    config = {"ui": {"hints": {"enabled": True, "delay_ms": 100}}}
    hm = HintManager(memory_manager, mock_i18n, config)
    parent = QWidget()
    parent.show()
    pos = parent.mapToGlobal(parent.rect().center())
    hm.show_tooltip("Test", pos, parent)
    mock_show.assert_called_once_with(pos, "Test", parent, msecShowTime=100)
