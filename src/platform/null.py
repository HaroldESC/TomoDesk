"""Degraded platform adapter for unsupported platforms."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .base import PlatformAdapter, PlatformCapabilities, WindowInfo

logger = logging.getLogger(__name__)


class NullAdapter(PlatformAdapter):
    """Degraded adapter: window, idle and taskbar features are unavailable.

    Decision on ``open_path``: it is implemented as a best-effort launch of the
    desktop opener (``xdg-open`` on POSIX, ``open`` on macOS) so callers such as
    the logs button keep working on Linux. It returns True only when the helper
    process starts successfully, False otherwise; it never raises.
    """

    @property
    def capabilities(self) -> PlatformCapabilities:
        """Only open_path is available (best-effort); the rest is unavailable."""
        return PlatformCapabilities(
            platform="null",
            window_enumeration=False,
            idle_time=False,
            taskbar_detection=False,
            taskbar_entry=False,
            open_path=True,
        )

    def get_active_window(self) -> Optional[WindowInfo]:
        """Window enumeration unsupported; degraded value: None."""
        return None

    def get_all_windows(self) -> list[WindowInfo]:
        """Window enumeration unsupported; degraded value: []."""
        return []

    def get_window_under_cursor(self) -> Optional[WindowInfo]:
        """Window enumeration unsupported; degraded value: None."""
        return None

    def get_idle_time_ms(self) -> int:
        """Idle detection unsupported; degraded value: 0."""
        return 0

    def taskbar_is_autohide(self) -> Optional[bool]:
        """Taskbar detection unsupported; degraded value: None."""
        return None

    def force_taskbar_entry(self, hwnd: int) -> bool:
        """Taskbar entry control unsupported; degraded value: False."""
        return False

    def open_path(self, path: str | Path) -> bool:
        """Best-effort open with xdg-open/open; degraded value: False."""
        helper = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.Popen([helper, str(path)])
            return True
        except Exception:
            logger.debug(f"open_path failed for {path}", exc_info=True)
            return False

    def popen_creationflags(self) -> int:
        """No creationflags outside Windows; degraded value: 0."""
        return 0
