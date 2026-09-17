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

    @staticmethod
    def _hwnd(win) -> Optional[int]:
        """Native window handle, usable to identify our own overlay."""
        handle = getattr(win, "_hWnd", None)
        if handle is None:
            return None
        try:
            return int(getattr(handle, "value", handle))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_dict(win) -> Optional[Dict[str, Any]]:
        """Normaliza una ventana de pygetwindow a un dict validado.

        Devuelve ``None`` para ventanas invalidas o sin geometria usable.
        """
        try:
            if not win or not win._rect or win.width <= 0 or win.height <= 0:
                return None
            return {
                "title": win.title,
                "bbox": (win.left, win.top, win.width, win.height),
                "hwnd": WindowManager._hwnd(win),
                "maximized": bool(getattr(win, "isMaximized", False)),
                "minimized": bool(getattr(win, "isMinimized", False)),
            }
        except Exception as e:
            logger.debug(f"_to_dict failed: {e}")
            return None

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        if not HAS_PYWINDOW:
            return None
        try:
            return self._to_dict(gw.getActiveWindow())
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
            for win in gw.getWindowsAt(x, y):
                result = self._to_dict(win)
                if result:
                    return result
        except Exception as e:
            logger.debug(f"get_window_under_cursor failed: {e}")
        return None

    def get_all_windows(self) -> list:
        if not HAS_PYWINDOW:
            return []
        try:
            return [
                d for d in (self._to_dict(w) for w in gw.getWindowsWithTitle(""))
                if d
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
