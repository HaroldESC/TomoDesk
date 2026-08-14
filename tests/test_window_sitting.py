import pytest
from unittest.mock import Mock, patch, MagicMock

from src.system.window_manager import WindowManager


def test_get_active_window_no_pygetwindow():
    with patch("src.system.window_manager.HAS_PYWINDOW", False):
        wm = WindowManager()
        assert wm.get_active_window() is None


def test_get_all_windows_empty():
    with patch("src.system.window_manager.HAS_PYWINDOW", True):
        with patch("src.system.window_manager.gw.getWindowsWithTitle", return_value=[]):
            wm = WindowManager()
            assert wm.get_all_windows() == []


def test_get_taskbar_geometry_no_pygetwindow():
    with patch("src.system.window_manager.HAS_PYWINDOW", False):
        wm = WindowManager()
        geo = wm.get_taskbar_geometry()
        assert "x" in geo and "y" in geo and "w" in geo and "h" in geo


class TestWindowSittingController:
    @pytest.fixture
    def overlay(self, qapp):
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        w.setFixedSize(150, 150)
        return w

    @pytest.fixture
    def controller(self, overlay):
        from src.gui.windows.overlay_window import WindowSittingController
        sprite = MagicMock()
        config = {
            "window_sitting": {
                "enabled": True,
                "target": "active_window",
                "transition_speed": 0.5,
                "fallback_position": "bottom-right",
            }
        }
        wm = MagicMock()
        ctrl = WindowSittingController(overlay, sprite, config, wm)
        return ctrl

    def test_controller_initialization(self, controller):
        assert controller.enabled is True
        assert controller.target_mode == "active_window"
        assert controller._animating is False
        assert controller._drag_pause is False

    def test_update_no_target_moves_to_fallback(self, controller):
        controller.wm.get_active_window.return_value = None
        controller.update()
        assert controller._animating is True

    def test_update_with_target(self, controller):
        controller.wm.get_active_window.return_value = {
            "title": "Test Window",
            "bbox": (100, 100, 800, 600),
        }
        controller.update()
        assert controller._animating is True

    def test_pause_on_drag(self, controller):
        controller.pause_on_drag()
        assert controller._drag_pause is True

    def test_update_blocked_during_drag_pause(self, controller):
        controller.pause_on_drag()
        controller._animating = False
        controller.update()
        assert controller._animating is False

    def test_set_focus_mode_disables(self, controller):
        controller.set_focus_mode(True)
        assert controller.enabled is False

    def test_set_focus_mode_enables(self, controller):
        controller.set_focus_mode(False)
        assert controller.enabled is True
