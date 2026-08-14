import json
import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent

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
    (locales / "en.json").write_text('{"menu": {"chat": "Chat"}}', encoding="utf-8")
    i18n = I18nManager(str(locales))
    i18n.set_language("en")
    return i18n


def test_overlay_creation(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    assert overlay.width() == 150
    assert overlay.height() == 150
    assert overlay.windowFlags() & Qt.WindowStaysOnTopHint
    assert overlay.testAttribute(Qt.WA_TranslucentBackground)
    overlay.close()


def test_position_persistence(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.move(100, 200)
    overlay.close()

    overlay2 = OverlayWindow(memory_manager, i18n, config)
    assert overlay2.pos() == QPoint(100, 200)
    overlay2.close()


def test_dragging(qapp, memory_manager, i18n):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)
    original_pos = overlay.pos()

    overlay.dragging = True
    overlay.drag_position = QPoint(10, 10)
    overlay.move(original_pos + QPoint(50, 50))
    overlay._save_position()

    saved = memory_manager.get_preference("overlay_position")
    assert saved is not None
    pos_data = json.loads(saved)
    assert pos_data["x"] == original_pos.x() + 50
    assert pos_data["y"] == original_pos.y() + 50
    overlay.close()


def test_double_click_signal(qapp, memory_manager, i18n, qtbot):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 150}}
    overlay = OverlayWindow(memory_manager, i18n, config)

    signal_emitted = False

    def on_double_click():
        nonlocal signal_emitted
        signal_emitted = True

    overlay.double_clicked.connect(on_double_click)

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPoint(10, 10),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier
    )
    overlay.mouseDoubleClickEvent(event)

    assert signal_emitted is True
    overlay.close()
