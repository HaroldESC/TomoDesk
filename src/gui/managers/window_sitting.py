import logging

from PySide6.QtCore import QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QGuiApplication

from src.system.window_manager import WindowManager

logger = logging.getLogger(__name__)


class WindowSittingController:
    """Manages the character sitting on windows."""

    def __init__(self, overlay_window, sprite, config, window_manager):
        self.overlay = overlay_window
        self.sprite = sprite
        self.config = config.get("window_sitting", {})
        self.wm = window_manager
        self.enabled = self.config.get("enabled", True)
        self.target_mode = self.config.get("target", "active_window")
        self.transition_speed = self.config.get("transition_speed", 0.5)
        self.fallback = self.config.get("fallback_position", "bottom-right")
        self._current_target = None
        self._animating = False
        self._drag_pause = False
        self._previous_target = None
        self._transition_hold_until = 0
        self._last_pos = None

    def update(self):
        if not self.enabled or self._drag_pause:
            return
        target = self._get_target_window()
        if target:
            sit_pos = self._compute_sitting_position(target)
            if self._last_pos and abs(sit_pos["x"] - self._last_pos["x"]) < 5 and abs(sit_pos["y"] - self._last_pos["y"]) < 5:
                return
            self._animate_to(sit_pos)
            self._last_pos = sit_pos
            self._previous_target = target
        else:
            self._move_to_fallback()

    def _get_target_window(self):
        if self.target_mode == "active_window":
            return self.wm.get_active_window()
        elif self.target_mode == "mouse_window":
            return self.wm.get_window_under_cursor()
        elif self.target_mode == "closest_window":
            return self._find_closest_window()
        elif self.target_mode == "fixed_spot":
            return None
        return None

    def _compute_sitting_position(self, window):
        sprite_h = self.overlay.height()
        visual_offset = 20
        return {
            "x": window["bbox"][0],
            "y": window["bbox"][1] - sprite_h + visual_offset,
        }

    def _animate_to(self, pos):
        if self._animating:
            return
        self._animating = True
        anim = QPropertyAnimation(self.overlay, b"geometry")
        anim.setDuration(int(self.transition_speed * 1000))
        anim.setStartValue(self.overlay.geometry())
        anim.setEndValue(QRect(pos["x"], pos["y"],
                               self.overlay.width(), self.overlay.height()))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._on_anim_finished)
        anim.start()

    def _on_anim_finished(self):
        self._animating = False

    def _move_to_fallback(self):
        if self.fallback == "bottom-right":
            screen = QGuiApplication.primaryScreen().geometry()
            x = screen.x() + screen.width() - 200
            y = screen.y() + screen.height() - 200
            if self._last_pos and abs(x - self._last_pos["x"]) < 5 and abs(y - self._last_pos["y"]) < 5:
                return
            self._last_pos = {"x": x, "y": y}
            target = QRect(x, y, self.overlay.width(), self.overlay.height())
            self._animate_to({"x": target.x(), "y": target.y()})

    def pause_on_drag(self):
        self._drag_pause = True
        QTimer.singleShot(5000, self._resume_after_drag)

    def _resume_after_drag(self):
        self._drag_pause = False

    def set_focus_mode(self, active: bool):
        if active:
            self.enabled = False
            self._move_to_fallback()
        else:
            self.enabled = True
