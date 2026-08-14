import logging
import zipfile
from pathlib import Path

MAX_PACK_ZIP_SIZE = 50 * 1024 * 1024

logger = logging.getLogger(__name__)


def is_safe_zip_member(name: str) -> bool:
    """Return True if the ZIP member name is safe to extract.

    Rejects absolute paths, ``..`` components and Windows-style
    backslash separators that could enable path traversal.
    """
    if Path(name).is_absolute() or ".." in Path(name).parts:
        return False
    if "\\" in name:
        return False
    normalized = name.replace("\\", "/")
    return all(part and part != ".." for part in normalized.split("/"))


def validate_zip_archive(path: Path) -> bool:
    """Validate a personality pack ZIP archive for safety and size."""
    try:
        if not path.exists() or path.stat().st_size > MAX_PACK_ZIP_SIZE:
            logger.warning(
                f"Rejected ZIP archive: {path} (missing or exceeds {MAX_PACK_ZIP_SIZE} bytes)"
            )
            return False
    except OSError as e:
        logger.warning(f"Failed to stat ZIP archive {path}: {e}")
        return False

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if "manifest.yaml" not in names:
                logger.warning(f"ZIP missing manifest.yaml: {path}")
                return False
            for name in names:
                if not is_safe_zip_member(name):
                    logger.warning(f"ZIP contains unsafe member: {name}")
                    return False
        return True
    except (zipfile.BadZipFile, OSError) as e:
        logger.warning(f"Invalid ZIP file {path}: {e}")
        return False
