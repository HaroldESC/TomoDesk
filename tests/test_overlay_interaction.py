import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from src.gui.windows.overlay_window import OverlayWindow


@pytest.fixture
def memory_manager(tmp_path):
    from src.memory.database import DatabaseManager
    from src.memory.chroma_manager import ChromaManager
    from src.memory.memory import MemoryManager

    db = DatabaseManager(str(tmp_path / "test.db"))
    db.initialize()
    chroma = ChromaManager(str(tmp_path / "chroma"), "all-MiniLM-L6-v2")
    chroma.initialize()
    config = {"memory": {"max_short_term_messages": 20}}
    mm = MemoryManager(db, chroma, config)
    return mm


@pytest.fixture
def i18n(tmp_path):
    from src.config.i18n import I18nManager
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "en.json").write_text(
        '{"interaction": {"no_last_message": "Hello! How can I help?", "inline_placeholder": "Type..."}}',
        encoding="utf-8"
    )
    i18n = I18nManager(str(locales))
    i18n.set_language("en")
    return i18n


def test_single_click_shows_bubble(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.set_last_assistant_message("Test message")
    overlay.show()
    QTest.qWait(100)

    center = overlay.rect().center()
    QTest.mouseClick(overlay, Qt.LeftButton, pos=center)
    QTest.qWait(100)

    assert overlay.bubble.isVisible()
    assert "Test message" in overlay.bubble.text_edit.toPlainText()
    overlay.close()


def test_single_click_default_greeting(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.show()
    QTest.qWait(100)

    center = overlay.rect().center()
    QTest.mouseClick(overlay, Qt.LeftButton, pos=center)
    QTest.qWait(100)

    assert overlay.bubble.isVisible()
    assert "Hello" in overlay.bubble.text_edit.toPlainText()
    overlay.close()


def test_double_click_emits_signal(qapp, memory_manager, i18n, qtbot):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.show()

    with qtbot.waitSignal(overlay.double_clicked, timeout=1000):
        center = overlay.rect().center()
        QTest.mouseDClick(overlay, Qt.LeftButton, pos=center)
    overlay.close()


def test_bubble_inline_input_on_bubble_click(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.show()
    overlay.bubble.show_text("Hello", animate=False)
    QTest.qWait(100)

    overlay.bubble.show_inline_input()
    QTest.qWait(50)

    assert overlay.bubble.input_edit.isVisible()
    overlay.close()


def test_bubble_message_sent_signal(qapp, memory_manager, i18n, qtbot):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)

    received = []

    def on_message(text):
        received.append(text)

    overlay.message_sent.connect(on_message)
    overlay.bubble.input_edit.setText("Hello from bubble")
    overlay.bubble._send_inline_message()

    assert len(received) == 1
    assert received[0] == "Hello from bubble"
    overlay.close()
