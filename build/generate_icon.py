"""Genera los iconos de la app a partir del estilo del sistema de diseño.

Dibuja un cuadrado redondeado con el acento ``#7B85D6`` y una ``T`` blanca
(igual que el icono del tray, ver ``src/gui/managers/tray_icon.py``) y exporta:

- ``build/assets/tomodesk.ico`` — multi-resolución (16/32/48/64/128/256) para el
  ejecutable Windows. El formato ICO se monta a mano con bloques PNG (válido
  desde Vista en adelante, evita depender de Pillow).
- ``build/assets/tomodesk.png`` — 256px para AppImage/.desktop y ventana.

Uso:
    python build/generate_icon.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

ACCENT = "#7B85D6"
WHITE = "#FFFFFF"
SIZES = (16, 32, 48, 64, 128, 256)

_ROOT = Path(__file__).resolve().parent
_ASSETS = _ROOT / "assets"


def _render_png(size: int) -> bytes:
    import tempfile

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    margin = max(1, size // 16)
    r = size - margin * 2
    painter.setBrush(QColor(ACCENT))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(margin, margin, r, r, r // 4, r // 4)
    painter.setPen(QColor(WHITE))
    fs = size * 9 // 16
    painter.setFont(QFont("Segoe UI", fs, QFont.Bold))
    painter.drawText(pix.rect(), Qt.AlignCenter, "T")
    painter.end()

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"icon_{size}.png"
        ok = pix.save(str(out), "PNG")
        if not ok or not out.exists():
            raise RuntimeError(f"No se pudo renderizar el icono a {size}px")
        return out.read_bytes()


def _ico_entries(images: dict[int, bytes]) -> bytes:
    """Monta un archivo ICO con bloques PNG para cada resolución."""
    header = bytes([0x00, 0x00, 0x01, 0x00])
    count = len(images)
    header += int.to_bytes(count, 2, "little")
    entries = bytearray()
    blobs = bytearray()
    offset = 6 + 16 * count
    for size in sorted(images):
        data = images[size]
        one_byte = 0 if size >= 256 else size
        entries += bytes([one_byte, one_byte, 0x00, 0x00])
        entries += int.to_bytes(1, 2, "little")  # planes
        entries += int.to_bytes(32, 2, "little")  # bit count
        entries += int.to_bytes(len(data), 4, "little")  # size in bytes
        entries += int.to_bytes(offset, 4, "little")  # offset in file
        blobs += data
        offset += len(data)
    return header + bytes(entries) + bytes(blobs)


def generate() -> None:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication(sys.argv)
    _ASSETS.mkdir(parents=True, exist_ok=True)

    images = {size: _render_png(size) for size in SIZES}
    (_ASSETS / "tomodesk.ico").write_bytes(_ico_entries(images))
    (_ASSETS / "tomodesk.png").write_bytes(images[256])

    print(f"Iconos generados en {_ASSETS}")


if __name__ == "__main__":
    generate()