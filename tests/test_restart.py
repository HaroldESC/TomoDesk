"""Pruebas del mecanismo de reinicio (relanzamiento del proceso hijo)."""

import sys
from unittest.mock import patch

import main as main_module
from main import _restart_command, _restart_process


def test_restart_command_source_mode_uses_sys_argv():
    with patch.object(main_module.paths, "is_frozen", return_value=False), \
         patch.object(main_module.sys, "argv", ["main.py", "--gui"]):
        args, flags = _restart_command()
    assert args[0] == sys.executable
    assert args[1:] == ["main.py", "--gui"]


def test_restart_command_frozen_omits_duplicated_exe_path():
    with patch.object(main_module.paths, "is_frozen", return_value=True), \
         patch.object(main_module.sys, "argv", [sys.executable]):
        args, flags = _restart_command()
    assert args == [sys.executable]


def test_restart_command_frozen_preserves_extra_args():
    with patch.object(main_module.paths, "is_frozen", return_value=True), \
         patch.object(main_module.sys, "argv", [sys.executable, "--cli"]):
        args, flags = _restart_command()
    assert args == [sys.executable, "--cli"]


def test_restart_command_windows_uses_no_window_flag():
    if sys.platform != "win32":
        return
    with patch.object(main_module.paths, "is_frozen", return_value=True), \
         patch.object(main_module.sys, "platform", "win32"):
        args, flags = _restart_command()
    assert flags & getattr(main_module.subprocess, "CREATE_NO_WINDOW", 0)


def test_restart_process_does_not_raise_on_failure():
    with patch("main.subprocess.Popen", side_effect=OSError("boom")):
        _restart_process()  # must not raise