import json
import os
from unittest.mock import MagicMock

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
from PySide6.QtWidgets import QApplication

from src.gui.windows.overlay_window import OverlayWindow, _POSITION_MARGIN


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


@pytest.fixture
def stub_memory():
    """Gestor de memoria sin dependencias: solo preferencias."""
    mm = MagicMock()
    mm.get_preference.return_value = None
    return mm


def _overlay_config(**ui):
    """Config mínima del overlay, con extras de la sección ``ui``."""
    section = {"character_size": 150}
    section.update(ui)
    return {"personality": {"name": "Tomo"}, "ui": section}


def _expected_default_pos(anchor: str, width: int, height: int) -> QPoint:
    area = QApplication.primaryScreen().availableGeometry()
    if anchor == "center":
        return QPoint(
            area.left() + (area.width() - width) // 2,
            area.top() + (area.height() - height) // 2,
        )
    x = (area.left() + _POSITION_MARGIN if "left" in anchor
         else area.right() - width - _POSITION_MARGIN)
    y = (area.top() + _POSITION_MARGIN if "top" in anchor
         else area.bottom() - height - _POSITION_MARGIN)
    return QPoint(x, y)


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


def test_set_focus_mode_propagates(qapp, memory_manager, i18n):
    config = {
        "personality": {"name": "Tomo"},
        "ui": {"character_size": 150},
        "window_sitting": {"enabled": True},
    }
    overlay = OverlayWindow(memory_manager, i18n, config)
    assert overlay.sitting_ctrl is not None
    overlay.set_focus_mode(True)
    assert overlay.sitting_ctrl.enabled is False
    overlay.set_focus_mode(False)
    assert overlay.sitting_ctrl.enabled is True
    overlay.close()


def test_apply_sitting_config(qapp, memory_manager, i18n):
    config = {
        "personality": {"name": "Tomo"},
        "ui": {"character_size": 150},
        "window_sitting": {"enabled": True, "target": "active_window"},
    }
    overlay = OverlayWindow(memory_manager, i18n, config)
    overlay.apply_sitting_config({"enabled": True, "target": "mouse_window"})
    assert overlay.sitting_ctrl.target_mode == "mouse_window"
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


class TestHotAppliedBubbleConfig:
    """Los ajustes de burbuja deben notarse sin reiniciar la aplicación."""

    def test_new_style_is_applied(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config(bubble_style="dark"))
        assert overlay.bubble.style.value == "dark"

        overlay.apply_bubble_config({"bubble_style": "comic"})

        assert overlay.bubble.style.value == "comic"
        overlay.close()

    def test_same_style_is_not_reapplied(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config(bubble_style="dark"))
        calls = []
        real_set_style = overlay.bubble.set_style
        overlay.bubble.set_style = lambda s: (calls.append(s), real_set_style(s))[1]

        ui = {"bubble_style": "round", "bubble_max_lines": 3,
              "bubble_fade_delay_ms": 2000, "bubble_typewriter_interval_ms": 50}
        overlay.apply_bubble_config(ui)
        overlay.apply_bubble_config(dict(ui))

        assert calls == ["round"]
        assert overlay.bubble.style.value == "round"
        assert overlay.bubble.max_lines == 3
        assert overlay.bubble.fade_delay_ms == 2000
        assert overlay.bubble.typewriter_interval_ms == 50
        assert overlay.bubble._anim_timer.interval() == 50
        overlay.close()

    @pytest.mark.parametrize("ui", [
        {},
        None,
        "no-es-un-diccionario",
        {"bubble_style": 42, "bubble_max_lines": "muchos",
         "bubble_fade_delay_ms": None, "bubble_typewriter_interval_ms": "rápido"},
    ])
    def test_empty_or_corrupt_config_is_ignored(self, stub_memory, i18n, ui):
        """Una config corrupta no puede tirar abajo el diálogo de Ajustes."""
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())
        before = overlay.bubble.style

        overlay.apply_bubble_config(ui)  # must not raise

        assert overlay.bubble.style is before
        assert overlay.bubble.max_lines == 5
        assert overlay.bubble.fade_delay_ms == 4000
        assert overlay.bubble.typewriter_interval_ms == 30
        overlay.close()

    def test_negative_values_are_clamped(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())

        overlay.apply_bubble_config({"bubble_max_lines": -4,
                                     "bubble_fade_delay_ms": -10,
                                     "bubble_typewriter_interval_ms": -5})

        assert overlay.bubble.max_lines >= 0
        assert overlay.bubble.fade_delay_ms >= 0
        assert overlay.bubble.typewriter_interval_ms == 30
        overlay.close()


class TestOverlayOpacity:
    # Windows cuantiza la opacidad a un byte (n/255), de ahí la tolerancia.
    OPACITY_ABS = 2.0 / 255.0

    def test_configured_opacity_is_applied_on_startup(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config(overlay_opacity=0.6))
        assert overlay.windowOpacity() == pytest.approx(0.6, abs=self.OPACITY_ABS)
        overlay.close()

    def test_missing_opacity_defaults_to_opaque(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())
        assert overlay.windowOpacity() == pytest.approx(1.0, abs=self.OPACITY_ABS)
        overlay.close()

    def test_hot_apply_sets_opacity(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())

        overlay.apply_overlay_opacity(0.5)

        assert overlay.windowOpacity() == pytest.approx(0.5, abs=self.OPACITY_ABS)
        overlay.close()

    def test_zero_is_clamped_to_a_visible_value(self, stub_memory, i18n):
        """Con 0 el personaje sería invisible e irrecuperable sin consola."""
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())

        overlay.apply_overlay_opacity(0)

        assert 0 < overlay.windowOpacity() <= 1.0
        overlay.close()

    def test_out_of_range_and_garbage_are_safe(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())

        overlay.apply_overlay_opacity(7.5)
        assert overlay.windowOpacity() == pytest.approx(1.0, abs=self.OPACITY_ABS)

        overlay.apply_overlay_opacity("opaco")  # must not raise
        assert overlay.windowOpacity() == pytest.approx(1.0, abs=self.OPACITY_ABS)
        overlay.close()

    def test_theme_change_preserves_opacity(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())
        overlay.apply_overlay_opacity(0.45)

        overlay.apply_theme("dark")

        assert overlay.windowOpacity() == pytest.approx(0.45, abs=self.OPACITY_ABS)
        overlay.close()


class TestDefaultOverlayPosition:
    @pytest.mark.parametrize(
        "anchor", ["bottom-right", "bottom-left", "top-right", "top-left", "center"]
    )
    def test_anchor_from_config_is_respected(self, stub_memory, i18n, anchor):
        overlay = OverlayWindow(
            stub_memory, i18n, _overlay_config(overlay_default_position=anchor)
        )

        assert overlay.pos() == _expected_default_pos(anchor, 150, 150)
        overlay.close()

    def test_default_anchor_is_bottom_right(self, stub_memory, i18n):
        overlay = OverlayWindow(stub_memory, i18n, _overlay_config())

        assert overlay.pos() == _expected_default_pos("bottom-right", 150, 150)
        overlay.close()

    def test_unknown_anchor_falls_back(self, stub_memory, i18n):
        overlay = OverlayWindow(
            stub_memory, i18n, _overlay_config(overlay_default_position="al-aire")
        )

        assert overlay.pos() == _expected_default_pos("bottom-right", 150, 150)
        overlay.close()

    def test_saved_position_wins_over_configured_default(self, stub_memory, i18n):
        saved = _expected_default_pos("center", 150, 150)
        stub_memory.get_preference.return_value = json.dumps(
            {"x": saved.x(), "y": saved.y()}
        )

        overlay = OverlayWindow(
            stub_memory, i18n, _overlay_config(overlay_default_position="top-left")
        )

        assert overlay.pos() == saved
        overlay.close()
