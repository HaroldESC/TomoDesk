"""Platform abstraction layer contracts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class WindowInfo:
    """Snapshot of a native window."""

    title: str
    bbox: tuple[int, int, int, int]  # (x, y, w, h)
    hwnd: Optional[int]
    maximized: bool
    minimized: bool


@dataclass(frozen=True)
class PlatformCapabilities:
    """Feature flags advertised by a platform adapter."""

    platform: str  # "windows", "null" (o nombre real)
    window_enumeration: bool
    idle_time: bool
    taskbar_detection: bool
    taskbar_entry: bool
    open_path: bool


class PlatformAdapter(ABC):
    """Contract: every method NEVER raises; returns documented degraded values."""

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        """Feature flags of this platform; always available."""

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Active window snapshot; degraded value: None."""

    @abstractmethod
    def get_all_windows(self) -> list[WindowInfo]:
        """Enumerated windows; degraded value: []."""

    @abstractmethod
    def get_window_under_cursor(self) -> Optional[WindowInfo]:
        """Window under the mouse cursor; degraded value: None."""

    @abstractmethod
    def get_idle_time_ms(self) -> int:
        """User idle time in milliseconds; degraded value: 0."""

    @abstractmethod
    def taskbar_is_autohide(self) -> Optional[bool]:
        """Whether the taskbar is auto-hidden; degraded value: None."""

    @abstractmethod
    def force_taskbar_entry(self, hwnd: int) -> bool:
        """Force a taskbar entry for hwnd; degraded value: False."""

    @abstractmethod
    def open_path(self, path: str | Path) -> bool:
        """Open path with the OS default handler; degraded value: False."""

    @abstractmethod
    def popen_creationflags(self) -> int:
        """creationflags for subprocess.Popen; degraded value: 0."""
