#!/usr/bin/env bash
# Build de TomoDesk para Linux: PyInstaller (one-folder) + appimagetool (AppImage).
#
# Uso:
#   bash build/build_unix.sh
#
# Requisitos:
#   - Python 3.12 + las deps Qt del sistema (libegl1, libgl1, libxkbcommon0,
#     libdbus-1-3, libfontconfig1, libxcb-cursor0, ...) ya instaladas.
#   - curl y FUSE2 (o se usa --appimage-extract-and-run si no hay FUSE).
#   - pyinstaller se instala automaticamente desde build/requirements-build.txt.
#
# Artefactos:
#   dist/TomoDesk/                        one-folder de PyInstaller
#   dist/TomoDesk-<version>-x86_64.AppImage

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=python
if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
fi

VERSION="$($PY - <<'EOF'
import re
from pathlib import Path
m = re.search(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"',
              Path("src/__init__.py").read_text())
if not m:
    raise SystemExit("No se encontro __version__ en src/__init__.py")
print(m.group(1))
EOF
)"

echo "== Build Linux: TomoDesk $VERSION =="

# 1. Dependencia de build (PyInstaller)
"$PY" -m pip install -q -r build/requirements-build.txt

# 2. Icono
"$PY" build/generate_icon.py

# 3. PyInstaller one-folder
"$PY" -m PyInstaller tomodesk.spec --noconfirm --clean
[ -f dist/TomoDesk/TomoDesk ] || { echo "Fallo el build de PyInstaller" >&2; exit 1; }

# 4. AppDir
APPDIR="$ROOT/build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a dist/TomoDesk/. "$APPDIR/usr/bin/"

cat > "$APPDIR/tomodesk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TomoDesk
Comment=TomoDesk - Desktop Companion
Exec=TomoDesk
Icon=tomodesk
Categories=Utility;Chat;
StartupWMClass=TomoDesk
Terminal=false
DESKTOP
cp build/assets/tomodesk.png "$APPDIR/tomodesk.png"
ln -sf usr/bin/TomoDesk "$APPDIR/AppRun"

# 5. appimagetool (descarga una sola vez a build/tools)
TOOLS="$ROOT/build/tools"
TOOL="$TOOLS/appimagetool-x86_64.AppImage"
mkdir -p "$TOOLS"
if [ ! -x "$TOOL" ]; then
    echo "Descargando appimagetool..."
    curl -fL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$TOOL"
fi

ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" \
    "dist/TomoDesk-$VERSION-x86_64.AppImage"

echo "== Build completado =="
echo "  AppImage: dist/TomoDesk-$VERSION-x86_64.AppImage"