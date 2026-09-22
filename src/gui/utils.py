"""Shared helpers for GUI windows."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

from src.platform import get_platform

logger = logging.getLogger(__name__)


def force_taskbar_entry(widget: QWidget) -> bool:
    """Force the dialog to get its own taskbar entry (Windows).

    Asks the platform adapter to set WS_EX_APPWINDOW on the widget's native
    handle. The handle is created first via ``winId()`` so the adapter always
    receives a valid hwnd. Returns the adapter outcome and never raises.
    """
    try:
        adapter = get_platform()
        if not adapter.capabilities.taskbar_entry:
            return False
        widget.winId()
        hwnd = int(widget.winId())
        return bool(adapter.force_taskbar_entry(hwnd))
    except Exception:
        logger.debug("force_taskbar_entry failed", exc_info=True)
        return False
