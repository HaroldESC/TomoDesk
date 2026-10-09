"""Fachada de deteccion de ventanas sobre el adapter de plataforma."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.platform import WindowInfo, get_platform

logger = logging.getLogger(__name__)

_FALLBACK_TASKBAR_HEIGHT = 40
_AUTOHIDE_TASKBAR_HEIGHT = 5


class WindowManager:
    """Abstracts window detection for sitting behavior.

    Delegates window queries to the platform adapter and exposes plain dicts
    with keys ``title`` (str), ``bbox`` (tuple x,y,w,h), ``hwnd`` (int|None),
    ``maximized`` (bool) and ``minimized`` (bool).
    """

    def __init__(self, adapter=None) -> None:
        """Crea la fachada.

        Args:
            adapter: ``PlatformAdapter`` inyectable (tests); por defecto el
                singleton de ``src.platform.get_platform()``.
        """
        self._adapter = adapter if adapter is not None else get_platform()

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
        """Convierte un ``WindowInfo`` o una ventana estilo-pygetwindow a dict.

        Devuelve ``None`` para ``None`` o geometria no usable.
        """
        try:
            if isinstance(win, WindowInfo):
                x, y, w, h = win.bbox
                if w <= 0 or h <= 0:
                    return None
                return {
                    "title": win.title,
                    "bbox": (x, y, w, h),
                    "hwnd": win.hwnd,
                    "maximized": bool(win.maximized),
                    "minimized": bool(win.minimized),
                }
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
        """Ventana activa como dict; degradado: None."""
        try:
            return self._to_dict(self._adapter.get_active_window())
        except Exception as e:
            logger.debug(f"get_active_window failed: {e}")
        return None

    def _get_cursor_pos(self) -> tuple[int, int]:
        """Posicion del cursor via el adapter; degradado: (0, 0)."""
        getter = getattr(self._adapter, "_get_cursor_pos", None)
        if callable(getter):
            try:
                return getter()
            except Exception as e:
                logger.debug(f"_get_cursor_pos failed: {e}")
        return 0, 0

    def get_window_under_cursor(self) -> Optional[Dict[str, Any]]:
        """Ventana bajo el cursor como dict; degradado: None."""
        try:
            return self._to_dict(self._adapter.get_window_under_cursor())
        except Exception as e:
            logger.debug(f"get_window_under_cursor failed: {e}")
        return None

    def get_all_windows(self) -> list:
        """Enumeracion actual de ventanas como dicts; degradado: []."""
        try:
            return [
                d
                for d in (self._to_dict(w) for w in self._adapter.get_all_windows())
                if d
            ]
        except Exception as e:
            logger.debug(f"get_all_windows failed: {e}")
            return []

    def get_taskbar_geometry(self) -> Dict[str, int]:
        """Geometria de la barra de tareas: autohide, por titulo o fallback.

        La geometria de pantalla la resuelve el adapter de plataforma, asi
        esta fachada no depende de una GUI activa.
        """
        try:
            if self._adapter.taskbar_is_autohide() is True:
                screen = self._adapter.primary_screen_geometry()
                if screen:
                    x, y, _w, h = screen
                    return {"x": x, "y": y + h - _AUTOHIDE_TASKBAR_HEIGHT,
                            "w": screen[2], "h": _AUTOHIDE_TASKBAR_HEIGHT}
        except Exception:
            logger.debug("taskbar_is_autohide failed", exc_info=True)
        for win in self.get_all_windows():
            if "taskbar" in win["title"].lower():
                x, y, w, h = win["bbox"]
                return {"x": x, "y": y, "w": w, "h": h}
        screen = self._adapter.primary_screen_geometry() or (0, 0, 1920, 1080)
        x, y, w, h = screen
        return {"x": x, "y": y + h - _FALLBACK_TASKBAR_HEIGHT,
                "w": w, "h": _FALLBACK_TASKBAR_HEIGHT}
