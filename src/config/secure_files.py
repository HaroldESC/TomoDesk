import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def secure_file(path: Path | str) -> None:
    """Restrict access to a file to the current user only.

    Best-effort operation that never raises: failures are logged and ignored.
    On POSIX the file mode is set to 0o600; on Windows the ACL is restricted
    to the current user via icacls with inheritance removed.
    """
    path = Path(path)
    if not path.exists():
        return
    try:
        if sys.platform == "win32":
            _secure_file_windows(path)
        else:
            os.chmod(path, 0o600)
    except Exception:
        logger.warning("Failed to secure file %s", path, exc_info=True)


def _current_user() -> str:
    """Return the current Windows username without raising."""
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USERNAME", os.environ.get("USER", ""))


def _secure_file_windows(path: Path) -> None:
    user = _current_user()
    if not user:
        logger.warning("Could not determine current user; skipping ACL for %s", path)
        return
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
        check=True,
        capture_output=True,
    )
