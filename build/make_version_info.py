"""Genera ``build/version_info.txt`` (VSVersionInfo) para el exe Windows.

Lee la version de ``src/__init__.py`` (``__version__``) y produce el archivo
que PyInstaller acepta en el parametro ``version=`` del spec.

Uso:
    python build/make_version_info.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OUT = Path(__file__).resolve().parent / "version_info.txt"

_PATTERN = re.compile(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')


def _current_version() -> str:
    init = _ROOT / "src" / "__init__.py"
    match = _PATTERN.search(init.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"No se encontro __version__ en {init}")
    return match.group(1)


def _build(version: str) -> str:
    major, minor, patch = (int(p) for p in version.split("."))
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [StringStruct('CompanyName', 'HaroldESC'),
           StringStruct('FileDescription', 'TomoDesk - Desktop Companion'),
           StringStruct('FileVersion', '{version}.0'),
           StringStruct('InternalName', 'TomoDesk'),
           StringStruct('OriginalFilename', 'TomoDesk.exe'),
           StringStruct('ProductName', 'TomoDesk'),
           StringStruct('ProductVersion', '{version}.0')]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


if __name__ == "__main__":
    _OUT.write_text(_build(_current_version()), encoding="utf-8")
    print(f"Version info escrito en {_OUT}")