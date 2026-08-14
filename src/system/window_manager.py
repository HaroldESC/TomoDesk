import logging
import ctypes
import ctypes.wintypes
from typing import Optional, Dict, Any

from PySide6.QtGui import QGuiApplication

logger = logging.getLogger(__name__)

try:
    import pygetwindow as gw
    HAS_PYWINDOW = True
except (ImportError, NotImplementedError):
    gw = None
    HAS_PYWINDOW = False
    logger.warning("pygetwindow not available. Window-sitting disabled.")


class WindowManager:
    """Abstracts window detection for sitting behavior."""

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        if not HAS_PYWINDOW:
            return None
        try:
            win = gw.getActiveWindow()
            if win and win._rect and win.width > 0 and win.height > 0:
                return {
                    "title": win.title,
                    "bbox": (win.left, win.top, win.width, win.height),
                }
        except Exception as e:
            logger.debug(f"get_active_window failed: {e}")
        return None

    @staticmethod
    def _get_cursor_pos():
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def get_window_under_cursor(self) -> Optional[Dict[str, Any]]:
        if not HAS_PYWINDOW:
            return None
        try:
            x, y = self._get_cursor_pos()
            wins = gw.getWindowsAt(x, y)
            for win in wins:
                if win._rect and win.width > 0 and win.height > 0:
                    return {
                        "title": win.title,
                        "bbox": (win.left, win.top, win.width, win.height),
                    }
        except Exception as e:
            logger.debug(f"get_window_under_cursor failed: {e}")
        return None

    def get_all_windows(self) -> list:
        if not HAS_PYWINDOW:
            return []
        try:
            return [
                {"title": w.title, "bbox": (w.left, w.top, w.width, w.height)}
                for w in gw.getWindowsWithTitle("")
                if w._rect and w.width > 0 and w.height > 0
            ]
        except Exception as e:
            logger.debug(f"get_all_windows failed: {e}")
            return []

    def get_taskbar_geometry(self):
        try:
            ABM_GETSTATE = 4
            ABS_AUTOHIDE = 1
            state = ctypes.windll.shell32.SHAppBarMessage(ABM_GETSTATE, None)
            if state == ABS_AUTOHIDE:
                screen = QGuiApplication.primaryScreen().geometry()
                return {"x": screen.x(), "y": screen.y() + screen.height() - 5,
                        "w": screen.width(), "h": 5}
        except Exception:
            pass
        if HAS_PYWINDOW:
            for win in gw.getWindowsWithTitle(""):
                if "taskbar" in win.title.lower():
                    return {"x": win.left, "y": win.top, "w": win.width, "h": win.height}
        screen = QGuiApplication.primaryScreen().geometry()
        return {"x": screen.x(), "y": screen.y() + screen.height() - 40,
                "w": screen.width(), "h": 40}
