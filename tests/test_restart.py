"""Pruebas del mecanismo de reinicio (relanzamiento del proceso hijo)."""

import os
import sys
from unittest.mock import patch

import main as main_module
from main import _restart_command, _restart_process


def _use_tmp_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module.paths, "user_data_dir", lambda: tmp_path)
    return main_module._lock_file_path()


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


def test_single_instance_lock_acquire_and_release(tmp_path, monkeypatch):
    lock_path = _use_tmp_lock(tmp_path, monkeypatch)
    lock = main_module._acquire_single_instance_lock()
    try:
        assert lock == lock_path
        assert lock_path.read_text(encoding="utf-8") == str(os.getpid())
    finally:
        main_module._release_single_instance_lock(lock)
    assert not lock_path.exists()


def test_single_instance_blocks_live_instance(tmp_path, monkeypatch):
    lock_path = _use_tmp_lock(tmp_path, monkeypatch)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(main_module, "_pid_alive", lambda pid: True)
    assert main_module._acquire_single_instance_lock() is None
    assert lock_path.exists()


def test_single_instance_reclaims_stale_lock(tmp_path, monkeypatch):
    lock_path = _use_tmp_lock(tmp_path, monkeypatch)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(main_module, "_pid_alive", lambda pid: False)
    lock = main_module._acquire_single_instance_lock()
    try:
        assert lock is not None
        assert lock_path.read_text(encoding="utf-8") == str(os.getpid())
    finally:
        main_module._release_single_instance_lock(lock)


def test_release_ignores_foreign_lock(tmp_path):
    lock_path = tmp_path / "tomodesk.lock"
    lock_path.write_text("123", encoding="utf-8")
    main_module._release_single_instance_lock(lock_path)
    assert lock_path.exists()