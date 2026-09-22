"""Platform abstraction layer."""
from __future__ import annotations

import sys
import threading

from .base import PlatformAdapter, PlatformCapabilities, WindowInfo

_lock = threading.Lock()
_adapter: PlatformAdapter | None = None


def get_platform() -> PlatformAdapter:
    """Return the process-wide adapter (lazily created, thread-safe, cached)."""
    global _adapter
    if _adapter is None:
        with _lock:
            if _adapter is None:
                if sys.platform == "win32":
                    from .windows import WindowsAdapter

                    _adapter = WindowsAdapter()
                else:
                    from .null import NullAdapter

                    _adapter = NullAdapter()
    return _adapter


def _set_platform(adapter: PlatformAdapter | None) -> None:
    """Test seam: inject a fake adapter (None resets to lazy default)."""
    global _adapter
    with _lock:
        _adapter = adapter


__all__ = [
    "PlatformAdapter",
    "PlatformCapabilities",
    "WindowInfo",
    "get_platform",
    "_set_platform",
]
