import pytest
from unittest.mock import Mock, patch, MagicMock

from src.system.window_manager import WindowManager


class _FakeWindow:
    def __init__(self, title, left, top, width, height, maximized=False, minimized=False):
        self.title = title
        self._rect = (left, top, width, height)
        self.left, self.top, self.width, self.height = left, top, width, height
        self.isMaximized = maximized
        self.isMinimized = minimized


def test_get_active_window_no_pygetwindow():
    with patch("src.system.window_manager.HAS_PYWINDOW", False):
        wm = WindowManager()
        assert wm.get_active_window() is None


def test_get_all_windows_empty():
    with patch("src.system.window_manager.HAS_PYWINDOW", True):
        with patch("src.system.window_manager.gw") as gw:
            gw.getWindowsWithTitle.return_value = []
            wm = WindowManager()
            assert wm.get_all_windows() == []


def test_get_taskbar_geometry_no_pygetwindow(qapp):
    with patch("src.system.window_manager.HAS_PYWINDOW", False):
        wm = WindowManager()
        geo = wm.get_taskbar_geometry()
        assert "x" in geo and "y" in geo and "w" in geo and "h" in geo


class TestWindowManagerState:
    def test_to_dict_includes_state_flags(self):
        win = _FakeWindow("W", 10, 20, 300, 200, maximized=True)
        data = WindowManager._to_dict(win)
        assert data["bbox"] == (10, 20, 300, 200)
        assert data["maximized"] is True
        assert data["minimized"] is False

    def test_to_dict_rejects_invalid_size(self):
        assert WindowManager._to_dict(_FakeWindow("W", 0, 0, 0, 0)) is None

    def test_get_active_window_reports_maximized(self):
        with patch("src.system.window_manager.HAS_PYWINDOW", True):
            with patch("src.system.window_manager.gw") as gw:
                gw.getActiveWindow.return_value = _FakeWindow(
                    "Max", 0, 0, 1920, 1080, maximized=True
                )
                data = WindowManager().get_active_window()
                assert data["maximized"] is True

    def test_get_all_windows_uses_normalizer(self):
        with patch("src.system.window_manager.HAS_PYWINDOW", True):
            with patch("src.system.window_manager.gw") as gw:
                gw.getWindowsWithTitle.return_value = [
                    _FakeWindow("A", 1, 2, 100, 100),
                    _FakeWindow("B", 0, 0, 0, 0),
                ]
                windows = WindowManager().get_all_windows()
                assert [w["title"] for w in windows] == ["A"]


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

    # ── Targeting ────────────────────────────────────────────────────────────

    def test_legacy_desktop_target_normalized(self, overlay):
        from src.gui.windows.overlay_window import WindowSittingController
        config = {"window_sitting": {"enabled": True, "target": "desktop"}}
        ctrl = WindowSittingController(overlay, MagicMock(), config, MagicMock())
        assert ctrl.target_mode == "fixed_spot"
        assert ctrl._get_target_window() is None

    def test_find_closest_window(self, controller):
        controller.overlay.move(0, 0)
        controller.wm.get_all_windows.return_value = [
            {"title": "far", "bbox": (2000, 2000, 100, 100)},
            {"title": "near", "bbox": (0, 0, 100, 100)},
        ]
        closest = controller._find_closest_window()
        assert closest["title"] == "near"

    def test_closest_mode_uses_finder(self, controller):
        controller.target_mode = "closest_window"
        controller.overlay.move(0, 0)
        controller.wm.get_all_windows.return_value = [
            {"title": "w", "bbox": (300, 300, 800, 600)},
        ]
        assert controller._get_target_window()["title"] == "w"

    def test_own_window_is_rejected(self, controller):
        from src.gui.managers.window_sitting import SELF_TARGET
        controller.overlay.move(50, 60)
        geo = controller.overlay.frameGeometry()
        own = {"title": "self", "bbox": (geo.x(), geo.y(), geo.width(), geo.height())}
        assert controller._is_own_window(own) is True
        controller.wm.get_active_window.return_value = own
        assert controller._get_target_window() is SELF_TARGET

    def test_own_window_matched_by_hwnd(self, controller):
        own_hwnd = controller._own_hwnd()
        assert own_hwnd is not None
        own = {"title": "self", "hwnd": own_hwnd, "bbox": (9999, 9999, 10, 10)}
        assert controller._is_own_window(own) is True
        other = {"title": "other", "hwnd": own_hwnd + 1, "bbox": (0, 0, 10, 10)}
        assert controller._is_own_window(other) is False

    def test_self_target_does_not_move(self, controller):
        from src.gui.managers.window_sitting import SELF_TARGET
        controller._animating = False
        controller.wm.get_active_window.return_value = {
            "title": "self", "hwnd": controller._own_hwnd(),
            "bbox": (0, 0, 10, 10),
        }
        controller.update()
        assert controller._animating is False

    # ── Positioning ──────────────────────────────────────────────────────────

    def test_fallback_positions_are_distinct(self, controller):
        from src.gui.managers.window_sitting import FALLBACK_POSITIONS
        points = {}
        for pos in FALLBACK_POSITIONS:
            controller.fallback = pos
            points[pos] = controller._fallback_point()
        assert points["top-left"]["x"] < points["top-right"]["x"]
        assert points["top-left"]["y"] < points["bottom-left"]["y"]
        assert points["bottom-right"]["x"] > points["bottom-left"]["x"]
        assert points["bottom-right"]["y"] > points["top-right"]["y"]

    def test_sitting_position_clamped_on_screen(self, controller):
        controller.overlay.move(0, 0)
        screen = controller._screen_for_bbox((0, 0, 100, 100))
        desktop = {
            "title": "Program Manager",
            "bbox": (screen.left(), screen.top(), screen.width(), screen.height()),
        }
        pos = controller._compute_sitting_position(desktop)
        assert pos["y"] >= screen.top()
        assert pos["x"] >= screen.left()

    def test_ineligible_windows_rejected(self, controller):
        assert controller._is_eligible({"bbox": (0, 0, 1, 1)}) is False
        assert controller._is_eligible({"bbox": (-32000, -32000, 160, 28)}) is False
        assert controller._is_eligible({"bbox": (0, 0, 100, 100)}) is True
        assert controller._is_eligible(
            {"bbox": (0, 0, 100, 100), "minimized": True}
        ) is True

    def test_closest_uses_edge_distance(self, controller):
        controller.overlay.move(0, 0)
        controller.wm.get_all_windows.return_value = [
            {"title": "far", "bbox": (5000, 5000, 100, 100)},
            {"title": "edge-near", "bbox": (100, 0, 50, 50)},
        ]
        assert controller._find_closest_window()["title"] == "edge-near"

    def test_closest_skips_minimized(self, controller):
        controller.overlay.move(0, 0)
        controller.wm.get_all_windows.return_value = [
            {"title": "min", "bbox": (-32000, -32000, 160, 28), "minimized": True},
            {"title": "real", "bbox": (300, 300, 800, 600)},
        ]
        assert controller._find_closest_window()["title"] == "real"

    def test_resolve_target_returns_anchor_for_ignored(self, controller):
        controller.maximized_behavior = 0
        controller.wm.get_active_window.return_value = {
            "title": "max", "bbox": (1, 2, 100, 100), "maximized": True,
        }
        target, anchor = controller._resolve_target()
        assert target is None
        assert anchor == (1, 2, 100, 100)

    def test_ignored_window_anchors_fallback(self, controller, monkeypatch):
        controller.config["maximized_behavior"] = 0
        controller.wm.get_active_window.return_value = {
            "title": "max", "bbox": (100, 100, 800, 600), "maximized": True,
        }
        captured = {}

        def fake_fallback(anchor=None):
            captured["anchor"] = anchor
            return {"x": 0, "y": 0}

        monkeypatch.setattr(controller, "_fallback_point", fake_fallback)
        controller.update()
        assert captured["anchor"] == (100, 100, 800, 600)

    def test_maximized_behavior(self, controller):
        win = {"bbox": (0, 0, 100, 100), "maximized": True}
        controller.maximized_behavior = 0
        assert controller._handle_maximized(win) is None
        controller.maximized_behavior = 1
        assert controller._handle_maximized(win) is not None

    def test_minimized_behavior_uses_taskbar(self, controller):
        win = {"bbox": (0, 0, 10, 10), "minimized": True}
        controller.minimized_behavior = 1
        controller.wm.get_taskbar_geometry.return_value = {
            "x": 0, "y": 1000, "w": 1920, "h": 40,
        }
        result = controller._handle_minimized(win)
        assert result["bbox"] == (0, 1000, 1920, 40)
        controller.minimized_behavior = 0
        assert controller._handle_minimized(win) is None

    # ── Config reload / animation ────────────────────────────────────────────

    def test_fallback_config_reload(self, controller):
        controller.wm.get_active_window.return_value = None
        controller.config["fallback_position"] = "top-left"
        controller.update()
        assert controller.fallback == "top-left"

    def test_animation_not_lost_on_new_target(self, controller):
        controller.wm.get_active_window.return_value = {
            "title": "a", "bbox": (100, 100, 800, 600),
        }
        controller.update()
        first_anim = controller._anim
        assert controller._animating is True

        controller.wm.get_active_window.return_value = {
            "title": "b", "bbox": (400, 400, 800, 600),
        }
        controller.update()
        assert controller._anim is not first_anim
        assert controller._animating is True
        assert controller._last_pos is not None

    def test_apply_config_updates_live(self, controller):
        controller.apply_config({
            "target": "mouse_window",
            "fallback_position": "top-left",
            "enabled": False,
        })
        assert controller.config["target"] == "mouse_window"
        assert controller.target_mode == "mouse_window"
        assert controller.fallback == "top-left"
        assert controller.enabled is False

    def test_focus_suppression_independent_of_config(self, controller):
        controller.set_focus_mode(True)
        assert controller.enabled is False
        controller.set_focus_mode(False)
        assert controller.enabled is True

        controller.config["enabled"] = False
        controller._refresh_config()
        assert controller.enabled is False
