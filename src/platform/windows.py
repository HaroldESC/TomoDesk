"""Windows platform adapter built on pygetwindow and ctypes."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .base import PlatformAdapter, PlatformCapabilities, WindowInfo

logger = logging.getLogger(__name__)

try:
    import pygetwindow as gw
except (ImportError, NotImplementedError):
    gw = None
    logger.warning("pygetwindow not available. Window enumeration disabled.")

_WS_EX_APPWINDOW = 0x00040000
_GWL_EXSTYLE = -20
_ABM_GETSTATE = 0x00000004
_ABS_AUTOHIDE = 0x00000001
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]


class WindowsAdapter(PlatformAdapter):
    """Windows implementation using pygetwindow and Win32 ctypes.

    Every method swallows errors and returns the degraded value documented
    in :class:`src.platform.base.PlatformAdapter`.
    """

    def __init__(self) -> None:
        self._idle_warning_logged = False

    @property
    def _has_pywindow(self) -> bool:
        """Whether pygetwindow was imported successfully."""
        return gw is not None

    @property
    def capabilities(self) -> PlatformCapabilities:
        """Windows feature flags; window_enumeration depends on pygetwindow."""
        return PlatformCapabilities(
            platform="windows",
            window_enumeration=self._has_pywindow,
            idle_time=True,
            taskbar_detection=True,
            taskbar_entry=True,
            open_path=True,
        )

    @staticmethod
    def _hwnd(win: Any) -> Optional[int]:
        """Native window handle, usable to identify our own overlay."""
        handle = getattr(win, "_hWnd", None)
        if handle is None:
            return None
        try:
            return int(getattr(handle, "value", handle))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_window_info(cls, win: Any) -> Optional[WindowInfo]:
        """Normaliza una ventana de pygetwindow a WindowInfo validado.

        Devuelve ``None`` para ventanas invalidas o sin geometria usable.
        """
        try:
            if not win or not win._rect or win.width <= 0 or win.height <= 0:
                return None
            return WindowInfo(
                title=win.title,
                bbox=(win.left, win.top, win.width, win.height),
                hwnd=cls._hwnd(win),
                maximized=bool(getattr(win, "isMaximized", False)),
                minimized=bool(getattr(win, "isMinimized", False)),
            )
        except Exception as e:
            logger.debug(f"_to_window_info failed: {e}")
            return None

    def get_active_window(self) -> Optional[WindowInfo]:
        """Active window snapshot; degraded value: None."""
        if not self._has_pywindow:
            return None
        try:
            return self._to_window_info(gw.getActiveWindow())
        except Exception as e:
            logger.debug(f"get_active_window failed: {e}")
        return None

    def _get_cursor_pos(self) -> tuple[int, int]:
        """Cursor coordinates via GetCursorPos."""
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def get_window_under_cursor(self) -> Optional[WindowInfo]:
        """Window under the cursor; degraded value: None."""
        if not self._has_pywindow:
            return None
        try:
            x, y = self._get_cursor_pos()
            for win in gw.getWindowsAt(x, y):
                result = self._to_window_info(win)
                if result:
                    return result
        except Exception as e:
            logger.debug(f"get_window_under_cursor failed: {e}")
        return None

    def get_all_windows(self) -> list[WindowInfo]:
        """All enumerable windows; degraded value: []."""
        if not self._has_pywindow:
            return []
        try:
            return [
                d
                for d in (
                    self._to_window_info(w) for w in gw.getWindowsWithTitle("")
                )
                if d
            ]
        except Exception as e:
            logger.debug(f"get_all_windows failed: {e}")
            return []

    def get_idle_time_ms(self) -> int:
        """User idle time in ms via GetLastInputInfo; degraded value: 0."""
        try:
            lii = _LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                return int(ctypes.windll.kernel32.GetTickCount()) - lii.dwTime
        except Exception:
            if not self._idle_warning_logged:
                logger.warning("Failed to get idle time, falling back to 0")
                self._idle_warning_logged = True
        return 0

    def taskbar_is_autohide(self) -> Optional[bool]:
        """Taskbar autohide state via SHAppBarMessage; degraded value: None."""
        try:
            state = ctypes.windll.shell32.SHAppBarMessage(_ABM_GETSTATE, None)
            return bool(state == _ABS_AUTOHIDE)
        except Exception:
            logger.debug("taskbar_is_autohide failed", exc_info=True)
            return None

    def force_taskbar_entry(self, hwnd: int) -> bool:
        """Set WS_EX_APPWINDOW on hwnd; degraded value: False."""
        if sys.platform != "win32":
            return False
        if not isinstance(hwnd, int) or hwnd <= 0:
            return False
        try:
            current = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, _GWL_EXSTYLE, current | _WS_EX_APPWINDOW
            )
            return True
        except Exception:
            logger.debug("force_taskbar_entry failed", exc_info=True)
            return False

    def open_path(self, path: str | Path) -> bool:
        """Open path via os.startfile; degraded value: False."""
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
        except Exception:
            logger.debug(f"open_path failed for {path}", exc_info=True)
            return False

    def popen_creationflags(self) -> int:
        """CREATE_NO_WINDOW | DETACHED_PROCESS on win32; degraded value: 0."""
        if sys.platform == "win32":
            return _CREATE_NO_WINDOW | _DETACHED_PROCESS
        return 0
