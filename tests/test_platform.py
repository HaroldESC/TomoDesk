"""Tests for the platform abstraction layer."""
import logging
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.platform import (
    PlatformAdapter,
    PlatformCapabilities,
    WindowInfo,
    _set_platform,
    get_platform,
)
from src.platform.null import NullAdapter

try:
    from src.platform.windows import WindowsAdapter
except Exception:  # pragma: no cover - adapter may not import on every platform
    WindowsAdapter = None

requires_windows_adapter = pytest.mark.skipif(
    WindowsAdapter is None, reason="WindowsAdapter not importable"
)


@pytest.fixture(autouse=True)
def reset_platform():
    _set_platform(None)
    yield
    _set_platform(None)


class _FakeWindow:
    def __init__(
        self,
        title,
        left,
        top,
        width,
        height,
        maximized=False,
        minimized=False,
        hwnd=None,
    ):
        self.title = title
        self._rect = (left, top, width, height)
        self.left, self.top, self.width, self.height = left, top, width, height
        self.isMaximized = maximized
        self.isMinimized = minimized
        if hwnd is not None:
            self._hWnd = hwnd


def _broken_windll():
    windll = MagicMock()
    windll.user32.GetLastInputInfo.side_effect = OSError("broken")
    windll.shell32.SHAppBarMessage.side_effect = OSError("broken")
    windll.user32.GetWindowLongW.side_effect = OSError("broken")
    return windll


class TestNullAdapter:
    def test_degraded_values(self):
        adapter = NullAdapter()
        assert adapter.get_active_window() is None
        assert adapter.get_all_windows() == []
        assert adapter.get_window_under_cursor() is None
        assert adapter.get_idle_time_ms() == 0
        assert adapter.taskbar_is_autohide() is None
        assert adapter.force_taskbar_entry(123) is False
        assert adapter.popen_creationflags() == 0

    def test_capabilities(self):
        caps = NullAdapter().capabilities
        assert isinstance(caps, PlatformCapabilities)
        assert caps.platform == "null"
        assert caps.window_enumeration is False
        assert caps.idle_time is False
        assert caps.taskbar_detection is False
        assert caps.taskbar_entry is False
        assert caps.open_path is True

    def test_is_platform_adapter(self):
        assert isinstance(NullAdapter(), PlatformAdapter)

    def test_open_path_success_linux(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        adapter = NullAdapter()
        with patch("src.platform.null.subprocess.Popen") as popen:
            assert adapter.open_path("/tmp/log.txt") is True
        popen.assert_called_once_with(["xdg-open", "/tmp/log.txt"])

    def test_open_path_success_darwin(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        adapter = NullAdapter()
        with patch("src.platform.null.subprocess.Popen") as popen:
            assert adapter.open_path("some/path") is True
        popen.assert_called_once_with(["open", "some/path"])

    def test_open_path_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        adapter = NullAdapter()
        with patch(
            "src.platform.null.subprocess.Popen",
            side_effect=FileNotFoundError("xdg-open"),
        ):
            assert adapter.open_path("/missing") is False

    def test_force_taskbar_entry_ignores_hwnd(self):
        assert NullAdapter().force_taskbar_entry(0) is False
        assert NullAdapter().force_taskbar_entry(-5) is False


@requires_windows_adapter
class TestWindowsAdapterBasics:
    def test_capabilities_with_pywindow(self):
        with patch("src.platform.windows.gw", MagicMock()):
            caps = WindowsAdapter().capabilities
        assert caps.platform == "windows"
        assert caps.window_enumeration is True
        assert caps.idle_time is True
        assert caps.taskbar_detection is True
        assert caps.taskbar_entry is True
        assert caps.open_path is True

    def test_capabilities_without_pywindow(self):
        with patch("src.platform.windows.gw", None):
            caps = WindowsAdapter().capabilities
        assert caps.window_enumeration is False

    def test_window_info_is_frozen(self):
        info = WindowInfo(title="W", bbox=(0, 0, 1, 1), hwnd=1, maximized=False, minimized=False)
        with pytest.raises(FrozenInstanceError):
            info.title = "other"

    def test_get_active_window(self):
        adapter = WindowsAdapter()
        fake = _FakeWindow("Editor", 10, 20, 800, 600, maximized=True, hwnd=99)
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getActiveWindow.return_value = fake
            info = adapter.get_active_window()
        assert info == WindowInfo(
            title="Editor",
            bbox=(10, 20, 800, 600),
            hwnd=99,
            maximized=True,
            minimized=False,
        )

    def test_get_active_window_unwraps_handle_value(self):
        adapter = WindowsAdapter()
        fake = _FakeWindow("H", 0, 0, 100, 100)
        fake._hWnd = SimpleNamespace(value=7)
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getActiveWindow.return_value = fake
            info = adapter.get_active_window()
        assert info is not None
        assert info.hwnd == 7

    def test_get_active_window_invalid_window(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getActiveWindow.return_value = _FakeWindow("W", 0, 0, 0, 0)
            assert adapter.get_active_window() is None

    def test_get_active_window_error_returns_none(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getActiveWindow.side_effect = RuntimeError("boom")
            assert adapter.get_active_window() is None

    def test_get_all_windows_filters_invalid(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getWindowsWithTitle.return_value = [
                _FakeWindow("A", 1, 2, 100, 100),
                _FakeWindow("B", 0, 0, 0, 0),
            ]
            windows = adapter.get_all_windows()
        gw_mock.getWindowsWithTitle.assert_called_once_with("")
        assert [w.title for w in windows] == ["A"]
        assert windows[0].bbox == (1, 2, 100, 100)

    def test_get_all_windows_error_returns_empty(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getWindowsWithTitle.side_effect = RuntimeError("boom")
            assert adapter.get_all_windows() == []

    def test_get_window_under_cursor(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock, patch.object(
            adapter, "_get_cursor_pos", return_value=(5, 7)
        ):
            gw_mock.getWindowsAt.return_value = [
                None,
                _FakeWindow("Under", 1, 2, 30, 40),
            ]
            info = adapter.get_window_under_cursor()
        gw_mock.getWindowsAt.assert_called_once_with(5, 7)
        assert info is not None
        assert info.title == "Under"

    def test_get_window_under_cursor_no_match(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock, patch.object(
            adapter, "_get_cursor_pos", return_value=(0, 0)
        ):
            gw_mock.getWindowsAt.return_value = []
            assert adapter.get_window_under_cursor() is None

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            ("get_active_window", None),
            ("get_all_windows", []),
            ("get_window_under_cursor", None),
        ],
    )
    def test_window_methods_without_pywindow(self, method, expected):
        with patch("src.platform.windows.gw", None):
            adapter = WindowsAdapter()
            assert getattr(adapter, method)() == expected


@requires_windows_adapter
class TestWindowsAdapterNative:
    def test_force_taskbar_entry_success(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        adapter = WindowsAdapter()
        windll = MagicMock()
        windll.user32.GetWindowLongW.return_value = 0x4
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.force_taskbar_entry(42) is True
        windll.user32.GetWindowLongW.assert_called_once_with(42, -20)
        windll.user32.SetWindowLongW.assert_called_once_with(42, -20, 0x40004)

    @pytest.mark.parametrize("hwnd", [0, -1])
    def test_force_taskbar_entry_invalid_hwnd(self, monkeypatch, hwnd):
        monkeypatch.setattr(sys, "platform", "win32")
        adapter = WindowsAdapter()
        windll = MagicMock()
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.force_taskbar_entry(hwnd) is False
        windll.user32.GetWindowLongW.assert_not_called()

    def test_force_taskbar_entry_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        adapter = WindowsAdapter()
        windll = _broken_windll()
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.force_taskbar_entry(42) is False

    def test_force_taskbar_entry_non_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        adapter = WindowsAdapter()
        windll = MagicMock()
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.force_taskbar_entry(42) is False
        windll.user32.GetWindowLongW.assert_not_called()

    @pytest.mark.parametrize(
        ("side_effect", "expected"),
        [(None, True), (FileNotFoundError("no startfile"), False)],
    )
    def test_open_path(self, side_effect, expected):
        adapter = WindowsAdapter()
        path = Path("C:/tmp/log.txt")
        with patch(
            "src.platform.windows.os.startfile", side_effect=side_effect, create=True
        ) as startfile:
            result = adapter.open_path(path)
        assert result is expected
        if expected:
            startfile.assert_called_once_with(str(path))

    @pytest.mark.parametrize(
        ("platform", "expected"),
        [("win32", 0x08000008), ("linux", 0)],
    )
    def test_popen_creationflags(self, monkeypatch, platform, expected):
        monkeypatch.setattr(sys, "platform", platform)
        assert WindowsAdapter().popen_creationflags() == expected

    @pytest.mark.parametrize(("state", "expected"), [(1, True), (0, False)])
    def test_taskbar_is_autohide(self, state, expected):
        adapter = WindowsAdapter()
        windll = MagicMock()
        windll.shell32.SHAppBarMessage.return_value = state
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.taskbar_is_autohide() is expected
        windll.shell32.SHAppBarMessage.assert_called_once_with(0x00000004, None)

    def test_taskbar_is_autohide_error_returns_none(self):
        adapter = WindowsAdapter()
        windll = _broken_windll()
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.taskbar_is_autohide() is None

    def test_get_idle_time_ms_success(self):
        adapter = WindowsAdapter()
        windll = MagicMock()
        windll.user32.GetLastInputInfo.return_value = 1
        windll.kernel32.GetTickCount.return_value = 5000
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.get_idle_time_ms() == 5000
        assert windll.user32.GetLastInputInfo.call_count == 1
        windll.kernel32.GetTickCount.assert_called_once()

    def test_get_idle_time_ms_no_input_returns_zero(self):
        adapter = WindowsAdapter()
        windll = MagicMock()
        windll.user32.GetLastInputInfo.return_value = 0
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            assert adapter.get_idle_time_ms() == 0
        windll.kernel32.GetTickCount.assert_not_called()

    def test_get_idle_time_ms_error_logs_warning_once(self, caplog):
        adapter = WindowsAdapter()
        windll = _broken_windll()
        with patch("src.platform.windows.ctypes.windll", windll, create=True):
            with caplog.at_level(logging.WARNING, logger="src.platform.windows"):
                assert adapter.get_idle_time_ms() == 0
                assert adapter.get_idle_time_ms() == 0
        warnings = [r for r in caplog.records if "idle time" in r.getMessage()]
        assert len(warnings) == 1


@requires_windows_adapter
class TestWindowsAdapterNeverRaises:
    def test_all_methods_with_broken_environment(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw", None), patch(
            "src.platform.windows.ctypes.windll", None, create=True
        ), patch(
            "src.platform.windows.os.startfile",
            side_effect=OSError("broken"),
            create=True,
        ):
            assert adapter.capabilities.platform == "windows"
            assert adapter.get_active_window() is None
            assert adapter.get_all_windows() == []
            assert adapter.get_window_under_cursor() is None
            assert adapter.get_idle_time_ms() == 0
            assert adapter.taskbar_is_autohide() is None
            assert adapter.force_taskbar_entry(42) is False
            assert adapter.force_taskbar_entry(0) is False
            assert adapter.open_path("whatever") is False
            assert isinstance(adapter.popen_creationflags(), int)

    def test_window_methods_with_failing_pywindow(self):
        adapter = WindowsAdapter()
        with patch("src.platform.windows.gw") as gw_mock:
            gw_mock.getActiveWindow.side_effect = RuntimeError("boom")
            gw_mock.getWindowsWithTitle.side_effect = RuntimeError("boom")
            gw_mock.getWindowsAt.side_effect = RuntimeError("boom")
            with patch.object(adapter, "_get_cursor_pos", return_value=(0, 0)):
                assert adapter.get_active_window() is None
                assert adapter.get_all_windows() == []
                assert adapter.get_window_under_cursor() is None


class TestPlatformFactory:
    def test_linux_returns_null(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        _set_platform(None)
        adapter = get_platform()
        assert isinstance(adapter, NullAdapter)

    @requires_windows_adapter
    def test_win32_returns_windows(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        _set_platform(None)
        adapter = get_platform()
        assert isinstance(adapter, WindowsAdapter)

    def test_adapter_is_cached(self):
        _set_platform(None)
        first = get_platform()
        assert get_platform() is first

    def test_set_platform_injects_fake(self):
        fake = NullAdapter()
        _set_platform(fake)
        assert get_platform() is fake

    def test_set_platform_none_resets(self):
        fake = NullAdapter()
        _set_platform(fake)
        _set_platform(None)
        adapter = get_platform()
        assert adapter is not fake
        assert isinstance(adapter, PlatformAdapter)
