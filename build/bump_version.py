"""Gestor de versiones (SemVer) de TomoDesk.

La fuente unica de verdad es ``src/__init__.py`` (``__version__``). Este script
centraliza el bump y mantiene sincronizados los duplicados:

- ``python build/bump_version.py 1.1.0``
    Actualiza ``src/__init__.py``, los badges de version del README y regenera
    ``build/version_info.txt`` (via ``make_version_info.py``).
- ``python build/bump_version.py --print``
    Imprime la version actual (``MAJOR.MINOR.PATCH``). Lo usa el guard de CI
    que verifica que el release tag coincida con ``src/__init__.py``.

Flujo de release recomendado (SemVer: patch para solo bugs, minor para
funcionalidad nueva retrocompatible):

    python build/bump_version.py 1.1.0
    git commit -am "chore: Bump version to 1.1.0"
    git tag -a v1.1.0 && git push origin v1.1.0
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_INIT = ROOT / "src" / "__init__.py"
README = ROOT / "README.md"

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_VERSION_LINE = re.compile(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"')
_README_VERSION_BADGE = re.compile(r"(badge/version-)[0-9]+\.[0-9]+\.[0-9]+(-blue)")
_README_STATUS_BADGE = re.compile(r"(badge/status-v)[0-9]+\.[0-9]+\.[0-9]+(-)")


def validate_semver(version: str) -> None:
    """Lanza ValueError si ``version`` no es MAJOR.MINOR.PATCH (sin prefijo v)."""
    if not _SEMVER.match(version):
        raise ValueError(
            f"Version invalida: {version!r} (formato esperado MAJOR.MINOR.PATCH)"
        )


def current_version() -> str:
    """Devuelve el valor actual de ``__version__`` en ``src/__init__.py``."""
    text = SRC_INIT.read_text(encoding="utf-8")
    match = _VERSION_LINE.search(text)
    if not match:
        raise ValueError(f"No se encontro __version__ en {SRC_INIT}")
    return match.group(1)


def new_src_init(text: str, version: str) -> str:
    """Reemplaza ``__version__`` en el contenido de ``src/__init__.py``."""
    if not _VERSION_LINE.search(text):
        raise ValueError("No se encontro __version__ para reemplazar")
    return _VERSION_LINE.sub(f'__version__ = "{version}"', text, count=1)


def _replace_badge(match: re.Match, version: str) -> str:
    return f"{match.group(1)}{version}{match.group(2)}"


def new_readme(text: str, version: str) -> str:
    """Actualiza los badges de version y status del README."""
    if not _README_VERSION_BADGE.search(text) or not _README_STATUS_BADGE.search(text):
        raise ValueError("README.md no contiene los badges de version esperados")
    out = _README_VERSION_BADGE.sub(lambda m: _replace_badge(m, version), text)
    return _README_STATUS_BADGE.sub(lambda m: _replace_badge(m, version), out)


def _regenerate_version_info() -> None:
    script = ROOT / "build" / "make_version_info.py"
    subprocess.run([sys.executable, str(script)], check=True)


def _apply(version: str) -> None:
    src = SRC_INIT.read_text(encoding="utf-8")
    SRC_INIT.write_text(new_src_init(src, version), encoding="utf-8")

    readme = README.read_text(encoding="utf-8")
    README.write_text(new_readme(readme, version), encoding="utf-8")

    _regenerate_version_info()


def main(argv: list[str]) -> int:
    if argv == ["--print"]:
        print(current_version())
        return 0
    if len(argv) != 1:
        print("Uso: python build/bump_version.py <MAJOR.MINOR.PATCH> | --print")
        return 2

    version = argv[0]
    try:
        validate_semver(version)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    if current_version() == version:
        print(f"La version ya es {version}; no se realiza ningun cambio.")
        return 0

    _apply(version)
    print(f"Version actualizada a {version}:")
    print(f"  - {SRC_INIT}")
    print(f"  - {README} (badges version/status)")
    print(f"  - build/version_info.txt (regenerado)")
    print()
    print(f"Recuerda: git commit -am \"chore: Bump version to {version}\"")
    print(f"          git tag -a v{version} && git push origin v{version}")
    print("Revisa manualmente ROADMAP.md (seccion Released) antes de publicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))