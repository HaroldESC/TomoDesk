import sys

import pytest

from src.config.secure_files import secure_file


def test_secure_file_missing_path_does_not_raise(tmp_path):
    missing = tmp_path / "does_not_exist.txt"
    secure_file(missing)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only behavior")
def test_secure_file_sets_0600_posix(tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("top secret")
    secure_file(target)
    mode = target.stat().st_mode & 0o777
    assert mode == 0o600


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only behavior")
def test_secure_file_uses_icacls_windows(mocker, tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("top secret")
    run = mocker.patch("src.config.secure_files.subprocess.run")
    mocker.patch("src.config.secure_files.os.getlogin", return_value="TestUser")
    secure_file(target)
    run.assert_called_once()
    args = run.call_args[0][0]
    assert args == ["icacls", str(target), "/inheritance:r", "/grant:r", "TestUser:F"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only behavior")
def test_secure_file_windows_never_raises_on_error(mocker, tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("top secret")
    run = mocker.patch("src.config.secure_files.subprocess.run")
    run.side_effect = OSError("boom")
    mocker.patch("src.config.secure_files.os.getlogin", return_value="TestUser")
    secure_file(target)
