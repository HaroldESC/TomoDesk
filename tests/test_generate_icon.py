"""Tests del generador de iconos ``build/generate_icon.py``.

Verifican que el glifo ``T`` se dibuja geométricamente (barra + asta), sin
depender de las fuentes del sistema. Con el plugin ``offscreen`` que usa CI la
base de fuentes de Qt está vacía, por lo que un glifo basado en ``QFont``
pintaría el recuadro de glifo ausente (tofu) en lugar de la letra.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

_BUILD_DIR = Path(__file__).resolve().parent.parent / "build"

# Umbrales para considerar un píxel "blanco" del glifo.
_WHITE_THRESHOLD = 200
_ALPHA_THRESHOLD = 128


def _load_generate_icon():
    path = _BUILD_DIR / "generate_icon.py"
    spec = importlib.util.spec_from_file_location("generate_icon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def icons():
    return _load_generate_icon()


def _image_from_png(data: bytes) -> QImage:
    image = QImage.fromData(data, "PNG")
    assert not image.isNull(), "No se pudo decodificar el PNG generado"
    return image


def _is_white(image: QImage, x: int, y: int) -> bool:
    color = image.pixelColor(x, y)
    return (
        color.red() > _WHITE_THRESHOLD
        and color.green() > _WHITE_THRESHOLD
        and color.blue() > _WHITE_THRESHOLD
        and color.alpha() > _ALPHA_THRESHOLD
    )


def _white_runs(image: QImage, y: int) -> list[tuple[int, int]]:
    """Devuelve ``(x_inicio, ancho)`` de cada tramo blanco contiguo de la fila ``y``."""
    runs: list[tuple[int, int]] = []
    start = None
    for x in range(image.width()):
        if _is_white(image, x, y):
            if start is None:
                start = x
        elif start is not None:
            runs.append((start, x - start))
            start = None
    if start is not None:
        runs.append((start, image.width() - start))
    return runs


def _white_bbox(image: QImage) -> tuple[int, int, int, int]:
    xs: list[int] = []
    ys: list[int] = []
    for y in range(image.height()):
        for x in range(image.width()):
            if _is_white(image, x, y):
                xs.append(x)
                ys.append(y)
    assert xs, "El render no contiene ningún píxel blanco"
    return min(xs), min(ys), max(xs), max(ys)


def _inner(size: int) -> int:
    """Lado del cuadrado interior (mismo cálculo que el módulo)."""
    return size - max(1, size // 16) * 2


def _expected_bar_width(icons, size: int) -> int:
    return max(
        icons.MIN_BAR_WIDTH,
        icons._round_px(icons.BAR_WIDTH_RATIO * _inner(size)),
    )


class TestTShapeAt256:
    def test_center_row_has_a_single_narrow_stem(self, qapp, icons):
        image = _image_from_png(icons._render_png(256))
        _, top, _, bottom = _white_bbox(image)

        runs = _white_runs(image, (top + bottom) // 2)

        # Una "T" tiene un único asta a media altura; un recuadro de glifo
        # ausente tendría dos tramos (los bordes izquierdo y derecho).
        assert len(runs) == 1, f"Se esperaba un único tramo, se obtuvo {runs}"
        start, width = runs[0]
        assert width < _expected_bar_width(icons, 256)

        left_margin = start
        right_margin = image.width() - (start + width)
        assert abs(left_margin - right_margin) <= 2

    def test_top_row_is_a_wide_bar(self, qapp, icons):
        image = _image_from_png(icons._render_png(256))
        _, top, _, _ = _white_bbox(image)

        runs = _white_runs(image, top)

        assert len(runs) == 1, f"Se esperaba un único tramo, se obtuvo {runs}"
        assert abs(runs[0][1] - _expected_bar_width(icons, 256)) <= 2


class TestLegibility:
    @pytest.mark.parametrize("size", [16, 32, 48, 64, 128, 256])
    def test_every_size_keeps_a_t_shape(self, qapp, icons, size):
        image = _image_from_png(icons._render_png(size))
        _, top, _, bottom = _white_bbox(image)

        center_y = (top + bottom) // 2
        runs = _white_runs(image, center_y)
        assert len(runs) == 1, f"{size}px: se esperaba un único tramo, se obtuvo {runs}"
        start, width = runs[0]

        left_margin = start
        right_margin = image.width() - (start + width)
        assert abs(left_margin - right_margin) <= 2

        top_runs = _white_runs(image, top)
        assert len(top_runs) == 1, f"{size}px: la barra superior no es contigua"
        assert top_runs[0][1] > width, f"{size}px: la barra no es más ancha que el asta"


class TestOffscreenRegression:
    def test_offscreen_render_is_t_shaped(self, tmp_path):
        """El render con ``QT_QPA_PLATFORM=offscreen`` (CI) sigue siendo una ``T``.

        Se ejecuta en un subproceso con el plugin forzado: en Linux CI no hay
        display, por lo que renderizar con el plugin por defecto fallaría.
        """
        out_png = tmp_path / "offscreen_256.png"
        script = (
            "import importlib.util, sys\n"
            "from pathlib import Path\n"
            "from PySide6.QtGui import QGuiApplication\n"
            "app = QGuiApplication([])\n"
            "spec = importlib.util.spec_from_file_location("
            "'generate_icon', sys.argv[1])\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "Path(sys.argv[2]).write_bytes(module._render_png(256))\n"
        )
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(_BUILD_DIR / "generate_icon.py"),
                str(out_png),
            ],
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert out_png.exists()

        image = QImage(str(out_png))
        assert not image.isNull()

        _, top, _, bottom = _white_bbox(image)
        runs = _white_runs(image, (top + bottom) // 2)
        assert len(runs) == 1, f"offscreen: se esperaba un único tramo, se obtuvo {runs}"
