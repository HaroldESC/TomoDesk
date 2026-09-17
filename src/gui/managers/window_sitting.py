import logging

from PySide6.QtCore import QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QGuiApplication

from src.system.window_manager import WindowManager

logger = logging.getLogger(__name__)

MODE_ACTIVE = "active_window"
MODE_MOUSE = "mouse_window"
MODE_CLOSEST = "closest_window"
MODE_FIXED = "fixed_spot"
MODE_DESKTOP_LEGACY = "desktop"

TARGET_MODES = (MODE_ACTIVE, MODE_MOUSE, MODE_CLOSEST, MODE_FIXED)
FALLBACK_POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left")

_TARGET_ALIASES = {MODE_DESKTOP_LEGACY: MODE_FIXED}
_MARGIN = 20
_VISUAL_OFFSET = 20
_DRAG_PAUSE_MS = 5000
_POSITION_TOLERANCE = 5
_MIN_WINDOW_SIZE = 16
_OFFSCREEN_LIMIT = -30000

#: Sentinel returned by ``_get_target_window`` when the only candidate is the
#: overlay itself; the controller must then stay put instead of jumping to the
#: fallback (which would cause an endless target/fallback oscillation).
SELF_TARGET = object()


class WindowSittingController:
    """Moves the overlay so the character sits on a target window.

    Target modes: ``active_window``, ``mouse_window``, ``closest_window`` and
    ``fixed_spot`` (always the configured fallback position). The legacy
    ``desktop`` value is normalised to ``fixed_spot``.
    """

    def __init__(self, overlay_window, sprite, config, window_manager):
        self.overlay = overlay_window
        self.sprite = sprite
        self.config = config.get("window_sitting", {})
        self.wm: WindowManager = window_manager
        self._config_enabled = True
        self._suppressed = False
        self._anim = None
        self._animating = False
        self._drag_pause = False
        self._last_pos = None
        self._refresh_config()

    @staticmethod
    def _normalize_target(target: str) -> str:
        return _TARGET_ALIASES.get(target, target)

    def _refresh_config(self):
        """Re-read settings so changes in Ajustes apply without restart."""
        self._config_enabled = self.config.get("enabled", True)
        self.target_mode = self._normalize_target(self.config.get("target", MODE_ACTIVE))
        self.transition_speed = self.config.get("transition_speed", 0.5)
        self.fallback = self.config.get("fallback_position", "bottom-right")
        self.maximized_behavior = int(self.config.get("maximized_behavior", 1))
        self.minimized_behavior = int(self.config.get("minimized_behavior", 0))

    def apply_config(self, config: dict) -> None:
        """Adopt the config pushed by Settings and reposition on next tick."""
        if isinstance(config, dict):
            self.config = config
        self._refresh_config()
        self._last_pos = None

    @property
    def enabled(self) -> bool:
        return self._config_enabled and not self._suppressed

    # ── Public API ───────────────────────────────────────────────────────────

    def update(self):
        self._refresh_config()
        if not self.enabled or self._drag_pause:
            return
        target, anchor = self._resolve_target()
        if target is SELF_TARGET:
            logger.debug("sitting mode=%s -> self (no move)", self.target_mode)
            return
        if target:
            pos = self._compute_sitting_position(target)
            logger.debug("sitting mode=%s target=%r -> (%s, %s)",
                         self.target_mode, target.get("title"), pos["x"], pos["y"])
        else:
            pos = self._fallback_point(anchor)
            logger.debug("sitting mode=%s -> fallback (%s, %s)",
                         self.target_mode, pos["x"], pos["y"])
        self._move_to(pos)

    def pause_on_drag(self):
        self._drag_pause = True
        QTimer.singleShot(_DRAG_PAUSE_MS, self._resume_after_drag)

    def set_focus_mode(self, active: bool):
        if active:
            if not self._suppressed:
                self._suppressed = True
                self._stop_animation()
                self._last_pos = None
                self._move_to_fallback()
        else:
            self._suppressed = False
            self._last_pos = None

    # ── Target resolution ────────────────────────────────────────────────────

    def _resolve_target(self):
        """Return ``(target, anchor_bbox)``.

        ``target`` is the window to sit on, ``SELF_TARGET`` or ``None``.
        ``anchor_bbox`` is the bbox of the window that was present but rejected
        (e.g. ignored by max/min behavior) so the fallback can be placed on that
        window's screen instead of the current one.
        """
        if self.target_mode == MODE_ACTIVE:
            win = self.wm.get_active_window()
        elif self.target_mode == MODE_MOUSE:
            win = self.wm.get_window_under_cursor()
        elif self.target_mode == MODE_CLOSEST:
            win = self._find_closest_window()
        else:
            return None, None
        if not win:
            return None, None
        if self._is_own_window(win):
            return SELF_TARGET, None
        if not self._is_eligible(win):
            logger.debug("target rejected (ineligible): %r bbox=%s",
                         win.get("title"), win.get("bbox"))
            return None, win.get("bbox")
        target = self._apply_state_behavior(win)
        if target is None:
            logger.debug(
                "target ignored by behavior: %r max=%s min=%s "
                "(maximized_behavior=%s minimized_behavior=%s)",
                win.get("title"), win.get("maximized"), win.get("minimized"),
                self.maximized_behavior, self.minimized_behavior,
            )
            return None, win.get("bbox")
        return target, target.get("bbox")

    def _get_target_window(self):
        """Backwards-compatible helper returning only the target."""
        return self._resolve_target()[0]

    def _is_eligible(self, window) -> bool:
        """Discard shell noise (tiny or off-screen windows)."""
        x, y, w, h = window["bbox"]
        if w < _MIN_WINDOW_SIZE or h < _MIN_WINDOW_SIZE:
            return False
        if window.get("minimized"):
            return True
        return x > _OFFSCREEN_LIMIT and y > _OFFSCREEN_LIMIT

    def _find_closest_window(self):
        center = self.overlay.frameGeometry().center()
        best = None
        best_dist = None
        candidates = 0
        for win in self.wm.get_all_windows():
            if self._is_own_window(win) or not self._is_eligible(win):
                continue
            if win.get("minimized"):
                continue
            candidates += 1
            dist = self._edge_distance(win["bbox"], center)
            if best_dist is None or dist < best_dist:
                best, best_dist = win, dist
        logger.debug("closest_window: %d candidates, chosen=%r",
                     candidates, best.get("title") if best else None)
        return best

    @staticmethod
    def _edge_distance(bbox, point) -> int:
        """Squared distance from a point to the nearest edge of a rectangle."""
        x, y, w, h = bbox
        dx = max(x - point.x(), 0, point.x() - (x + w))
        dy = max(y - point.y(), 0, point.y() - (y + h))
        return dx * dx + dy * dy

    def _is_own_window(self, window) -> bool:
        hwnd = window.get("hwnd")
        if hwnd is not None:
            own_hwnd = self._own_hwnd()
            if own_hwnd is not None:
                return int(hwnd) == own_hwnd
        # Geometry fallback (e.g. mocked windows in tests).
        try:
            geo = self.overlay.frameGeometry()
        except Exception:
            return False
        x, y, w, h = window["bbox"]
        return (
            abs(x - geo.x()) <= _POSITION_TOLERANCE
            and abs(y - geo.y()) <= _POSITION_TOLERANCE
            and abs(w - geo.width()) <= _POSITION_TOLERANCE
            and abs(h - geo.height()) <= _POSITION_TOLERANCE
        )

    def _own_hwnd(self):
        try:
            return int(self.overlay.winId())
        except Exception:
            return None

    def _apply_state_behavior(self, window):
        if window.get("minimized"):
            return self._handle_minimized(window)
        if window.get("maximized"):
            return self._handle_maximized(window)
        return window

    def _handle_maximized(self, window):
        # Visibility is guaranteed by the screen clamp in
        # _compute_sitting_position; 0 means "ignore maximized windows".
        return window if self.maximized_behavior == 1 else None

    def _handle_minimized(self, window):
        if self.minimized_behavior != 1:
            return None
        taskbar = self.wm.get_taskbar_geometry()
        if not taskbar:
            return None
        return {**window, "bbox": (taskbar["x"], taskbar["y"], taskbar["w"], taskbar["h"])}

    # ── Geometry ─────────────────────────────────────────────────────────────

    def _compute_sitting_position(self, window):
        x, y, w, h = window["bbox"]
        # Clamp to the screen that owns the target so the character stays
        # visible even when monitors are offset (not aligned in a rectangle).
        screen = self._screen_for_bbox((x, y, w, h))
        pos_x = x
        pos_y = y - self.overlay.height() + _VISUAL_OFFSET
        max_x = screen.left() + screen.width() - self.overlay.width()
        max_y = screen.top() + screen.height() - self.overlay.height()
        return {
            "x": max(screen.left(), min(pos_x, max_x)),
            "y": max(screen.top(), min(pos_y, max_y)),
        }

    def _fallback_point(self, anchor_bbox=None):
        # When a window was present but ignored, anchor the fallback to that
        # window's screen so the character still follows it across monitors.
        bbox = anchor_bbox if anchor_bbox is not None else self.overlay.frameGeometry().getRect()
        screen = self._screen_for_bbox(bbox)
        w, h = self.overlay.width(), self.overlay.height()
        if "left" in self.fallback:
            x = screen.left() + _MARGIN
        else:
            x = screen.left() + screen.width() - w - _MARGIN
        if "top" in self.fallback:
            y = screen.top() + _MARGIN
        else:
            y = screen.top() + screen.height() - h - _MARGIN
        return {"x": x, "y": y}

    def _screen_for_bbox(self, bbox) -> QRect:
        x, y, w, h = bbox
        screen = QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    # ── Animation ────────────────────────────────────────────────────────────

    def _move_to(self, pos):
        if self._is_same_position(pos):
            return
        self._last_pos = pos
        self._animate_to(pos)

    def _is_same_position(self, pos) -> bool:
        if not self._last_pos:
            return False
        return (
            abs(pos["x"] - self._last_pos["x"]) < _POSITION_TOLERANCE
            and abs(pos["y"] - self._last_pos["y"]) < _POSITION_TOLERANCE
        )

    def _animate_to(self, pos):
        self._stop_animation()
        self._animating = True
        anim = QPropertyAnimation(self.overlay, b"geometry")
        anim.setDuration(max(1, int(self.transition_speed * 1000)))
        anim.setStartValue(self.overlay.geometry())
        anim.setEndValue(QRect(pos["x"], pos["y"], self.overlay.width(), self.overlay.height()))
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self._on_anim_finished)
        self._anim = anim
        anim.start()

    def _stop_animation(self):
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self._animating = False

    def _on_anim_finished(self):
        self._anim = None
        self._animating = False

    def _move_to_fallback(self):
        self._move_to(self._fallback_point())

    def _resume_after_drag(self):
        self._drag_pause = False
