"""Genera los iconos de la app a partir del estilo del sistema de diseño.

Dibuja un cuadrado redondeado con el acento ``#7B85D6`` y una ``T`` blanca
(igual que el icono del tray, ver ``src/gui/managers/tray_icon.py``) y exporta:

- ``build/assets/tomodesk.ico`` — multi-resolución (16/32/48/64/128/256) para el
  ejecutable Windows. El formato ICO se monta a mano con bloques PNG (válido
  desde Vista en adelante, evita depender de Pillow).
- ``build/assets/tomodesk.png`` — 256px para AppImage/.desktop y ventana.

La ``T`` se dibuja geométricamente (barra superior + asta vertical) en lugar de
usar ``QFont``/``drawText``. Con el plugin de plataforma ``offscreen`` —que usa
el job ``release`` de CI— la base de fuentes de Qt queda vacía (0 familias), por
lo que ``Segoe UI`` no existe y Qt pintaría el recuadro de glifo ausente (tofu)
en vez de la letra. El glifo geométrico no depende de ninguna fuente del sistema
y produce el mismo resultado en local y en CI.

Constantes de proporción (respecto al cuadrado interior ``inner = r``):

- ``BAR_WIDTH_RATIO``: ancho de la barra horizontal superior.
- ``BAR_HEIGHT_RATIO``: alto de la barra horizontal superior.
- ``STEM_WIDTH_RATIO``: ancho del asta vertical.
- ``GLYPH_HEIGHT_RATIO``: alto total del glifo (desde la barra hasta el pie).
- ``GLYPH_TOP_RATIO``: desplazamiento vertical del borde superior del glifo
  respecto al borde superior del cuadrado interior.

Los mínimos ``MIN_*`` garantizan que el glifo siga siendo legible a 16px. Además,
las aristas del glifo se alinean a la rejilla de píxeles de dispositivo: sin esa
alineación un asta de 1px centrada en una coordenada fraccionaria se reparte
entre dos columnas al 50% y se desvanece por debajo del blanco puro.

Uso:
    python build/generate_icon.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ACCENT = "#7B85D6"
WHITE = "#FFFFFF"
SIZES = (16, 32, 48, 64, 128, 256)

# Proporciones del glifo, medidas sobre el render bueno de 256px.
BAR_WIDTH_RATIO = 0.290
BAR_HEIGHT_RATIO = 0.045
STEM_WIDTH_RATIO = 0.05
GLYPH_HEIGHT_RATIO = 0.415
GLYPH_TOP_RATIO = 0.330

# Mínimos en píxeles de dispositivo para mantener la legibilidad a 16px.
MIN_BAR_WIDTH = 3
MIN_BAR_HEIGHT = 1
MIN_STEM_WIDTH = 1
MIN_GLYPH_HEIGHT = 5

_ROOT = Path(__file__).resolve().parent
_ASSETS = _ROOT / "assets"


def _round_px(value: float) -> int:
    """Redondea a la mitad hacia arriba (evita el redondeo bancario de ``round``)."""
    return int(value + 0.5)


def _render_png(size: int) -> bytes:
    import tempfile

    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QPainter, QPixmap

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = max(1, size // 16)
    r = size - margin * 2
    painter.setBrush(QColor(ACCENT))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(margin, margin, r, r, r // 4, r // 4)

    # Glifo ``T`` dibujado con primitivas, sin depender de fuentes del sistema.
    # Las medidas se redondean a píxeles de dispositivo para que los trazos finos
    # queden nítidos (blanco puro) también a 16px.
    inner = float(r)
    bar_w = max(MIN_BAR_WIDTH, _round_px(BAR_WIDTH_RATIO * inner))
    bar_h = max(MIN_BAR_HEIGHT, _round_px(BAR_HEIGHT_RATIO * inner))
    stem_w = max(MIN_STEM_WIDTH, _round_px(STEM_WIDTH_RATIO * inner))
    glyph_h = max(MIN_GLYPH_HEIGHT, _round_px(GLYPH_HEIGHT_RATIO * inner))
    top = _round_px(margin + GLYPH_TOP_RATIO * inner)
    left_bar = _round_px(margin + (inner - bar_w) / 2)
    left_stem = _round_px(margin + (inner - stem_w) / 2)

    painter.setBrush(QColor(WHITE))
    painter.drawRect(QRect(left_bar, top, bar_w, bar_h))
    painter.drawRect(QRect(left_stem, top, stem_w, glyph_h))
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

    # Fuerza el plugin offscreen por defecto para que el render sea idéntico en
    # local y en CI (en CI/Linux no hay display disponible).
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QGuiApplication(sys.argv)
    _ASSETS.mkdir(parents=True, exist_ok=True)

    images = {size: _render_png(size) for size in SIZES}
    (_ASSETS / "tomodesk.ico").write_bytes(_ico_entries(images))
    (_ASSETS / "tomodesk.png").write_bytes(images[256])

    print(f"Iconos generados en {_ASSETS}")


if __name__ == "__main__":
    generate()
