#!/usr/bin/env bash
# Build de TomoDesk para Linux: PyInstaller (one-folder) + appimagetool (AppImage).
#
# Uso:
#   bash build/build_unix.sh [--standard]
#
#   (por defecto)  instala llama-cpp-python (requirements-llama.txt) antes de
#                  empaquetar, de modo que el binario incluye el provider de IA
#                  local (llama.cpp). El modelo GGUF NO se bundlea (licencia):
#                  se descarga con el asistente de primera ejecucion o desde
#                  Ajustes.
#   --standard     NO instala llama-cpp-python: binario mas ligero que oculta la
#                  opcion de IA local en el asistente. Solo para pruebas.
#   --full         obsoleto; equivale al comportamiento por defecto.
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

STANDARD=0
for arg in "$@"; do
    case "$arg" in
        --standard) STANDARD=1 ;;
        --full) echo "Aviso: --full es obsoleto; la IA local es el comportamiento por defecto" >&2 ;;
        *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
    esac
done

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

# 1b. Runtime local de IA (llama-cpp-python). Por defecto SI se incluye: el
#     asistente de primera ejecucion ofrece IA local y el binario debe poder
#     servirla. --standard genera un binario sin ella a proposito.
if [ "$STANDARD" -eq 1 ]; then
    echo "Build estandar (--standard): sin llama-cpp-python, la IA local se ocultara en el asistente."
else
    echo "Instalando llama-cpp-python (provider de IA local)..."
    "$PY" -m pip install -q -r requirements-llama.txt
    # Hace que tomodesk.spec aborte si llama_cpp no acaba en el bundle.
    export TOMODESK_REQUIRE_LLAMA_CPP=1
fi

# 2. Icono
"$PY" build/generate_icon.py

# 3. PyInstaller one-folder
"$PY" -m PyInstaller tomodesk.spec --noconfirm --clean
[ -f dist/TomoDesk/TomoDesk ] || { echo "Fallo el build de PyInstaller" >&2; exit 1; }

# 3b. Verificacion post-build del runtime local: un release no debe salir sin el
#     provider que el asistente ofrece descargar.
if [ -d dist/TomoDesk/_internal/llama_cpp ]; then
    LLAMA_BUNDLED="si"
else
    LLAMA_BUNDLED="no"
fi
if [ "$STANDARD" -eq 1 ]; then
    [ "$LLAMA_BUNDLED" = "si" ] && echo "Aviso: --standard pedido pero llama_cpp acabo en el bundle" >&2
else
    [ "$LLAMA_BUNDLED" = "si" ] || { echo "El build debia incluir la IA local pero dist/TomoDesk/_internal/llama_cpp no existe" >&2; exit 1; }
fi

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
echo "  IA local: $LLAMA_BUNDLED"
echo "  AppImage: dist/TomoDesk-$VERSION-x86_64.AppImage"