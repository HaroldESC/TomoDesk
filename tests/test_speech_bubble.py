import os
import re

from unittest.mock import MagicMock

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.gui.widgets.speech_bubble import SpeechBubble


def _wheel_event(angle_y: int) -> QWheelEvent:
    """
    Construye un QWheelEvent vertical.

    Qt usa angleDelta().y() negativo para "rueda hacia abajo" (avanzar en el
    contenido) y positivo para "rueda hacia arriba" (retroceder).
    """
    return QWheelEvent(
        QPointF(10.0, 10.0),   # pos
        QPointF(10.0, 10.0),   # globalPos
        QPoint(0, 0),          # pixelDelta
        QPoint(0, angle_y),    # angleDelta
        Qt.NoButton,
        Qt.NoModifier,
        Qt.NoScrollPhase,
        False,                # inverted
    )


def test_bubble_creation(qapp):
    bubble = SpeechBubble(style="dark")
    assert bubble.style.value == "dark"
    assert bubble.max_lines == 5
    assert not bubble.isVisible()


def test_show_thinking(qapp):
    bubble = SpeechBubble()
    bubble.show_thinking()
    assert bubble.isVisible()
    assert "..." in bubble.text_edit.toPlainText()
    bubble.hide_bubble()


def test_show_text(qapp):
    bubble = SpeechBubble(typewriter_interval_ms=10)
    bubble.show_text("Hello world", animate=True)
    assert bubble.isVisible()
    bubble.hide_bubble()


def test_show_text_no_animate(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello world", animate=False)
    assert bubble.isVisible()
    assert "Hello world" in bubble.text_edit.toPlainText()
    bubble.hide_bubble()


def test_comic_style(qapp):
    bubble = SpeechBubble(style="comic")
    assert bubble.style.value == "comic"
    bubble.set_style("dark")
    assert bubble.style.value == "dark"


def test_hide_bubble(qapp):
    bubble = SpeechBubble()
    bubble.show_thinking()
    assert bubble.isVisible()
    bubble.hide_bubble()
    assert not bubble.isVisible()


def test_text_truncation(qapp):
    bubble = SpeechBubble(max_lines=2)
    long_text = "line1\nline2\nline3\nline4"
    bubble.show_text(long_text, animate=False)
    displayed = bubble.text_edit.toPlainText()
    assert "..." in displayed
    assert "line3" not in displayed
    assert "line4" not in displayed
    bubble.hide_bubble()


def test_single_click_emits_clicked(qapp, qtbot):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    with qtbot.waitSignal(bubble.clicked, timeout=1000):
        QTest.mouseClick(bubble, Qt.LeftButton, pos=bubble.rect().center())
    bubble.hide_bubble()


def test_double_click_emits_double_clicked(qapp, qtbot):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    with qtbot.waitSignal(bubble.double_clicked, timeout=1000):
        QTest.mouseDClick(bubble, Qt.LeftButton, pos=bubble.rect().center())
    bubble.hide_bubble()


def test_message_sent_signal(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    received = []

    def on_message(text):
        received.append(text)

    bubble.message_sent.connect(on_message)
    bubble.message_sent.emit("Test reply")

    assert len(received) == 1
    assert received[0] == "Test reply"
    bubble.hide_bubble()


def test_send_inline_message(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    received = []

    def on_message(text):
        received.append(text)

    bubble.message_sent.connect(on_message)
    bubble.input_edit.setText("Test reply")
    bubble._send_inline_message()

    assert len(received) == 1
    assert received[0] == "Test reply"
    assert not bubble.input_edit.isVisible()
    bubble.hide_bubble()


def test_show_inline_input(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    bubble.show_inline_input()
    assert bubble.input_edit.isVisible()
    bubble.hide_bubble()


def test_hide_bubble_hides_inline_input(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    bubble.show_inline_input()
    assert bubble.input_edit.isVisible()

    bubble.hide_bubble()
    assert not bubble.input_edit.isVisible()
    assert not bubble.isVisible()


def test_inline_input_hides_on_escape(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    bubble.show_inline_input()
    assert bubble.input_edit.isVisible()

    QTest.keyPress(bubble.input_edit, Qt.Key_Escape)
    QTest.qWait(50)

    assert not bubble.input_edit.isVisible()
    bubble.hide_bubble()


def test_adjust_size_non_thinking(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Hello world", animate=False)
    assert bubble.width() >= bubble.minimumWidth()
    assert bubble.height() > 30
    bubble.hide_bubble()


def test_resized_signal(qapp, qtbot):
    bubble = SpeechBubble()
    bubble.show_text("Hello", animate=False)
    bubble.show()
    QTest.qWait(50)

    with qtbot.waitSignal(bubble.resized, timeout=1000):
        bubble.resize(300, 100)
    bubble.hide_bubble()


@pytest.mark.parametrize("style", ["dark", "comic", "flat", "round"])
def test_every_style_constructs(qapp, style):
    """The Settings combo can never offer a style the widget rejects."""
    bubble = SpeechBubble(style=style)
    assert bubble.style.value == style
    assert bubble._radius > 0


def test_flat_style_has_hard_corners(qapp):
    from src.gui.widgets.speech_bubble import BubbleStyle
    bubble = SpeechBubble(style="flat")
    assert bubble._radius < 8
    bubble.show_text("Hello", animate=False)
    bubble.resize(200, 80)
    path = bubble._build_path()
    assert path is not None


def test_round_style_has_soft_corners(qapp):
    bubble = SpeechBubble(style="round")
    assert bubble._radius > 15
    bubble.resize(200, 80)
    assert bubble._build_path() is not None


def test_unknown_style_falls_back_to_dark(qapp):
    """A stale config value must not crash the app at startup."""
    bubble = SpeechBubble(style="does_not_exist")
    assert bubble.style.value == "dark"
    assert bubble._radius == 12.0


# ── Geometría del input inline (Design.md §3.3) ──────────────────────────────

def _input_block(qss: str) -> str:
    """Devuelve el bloque ``QLineEdit`` (sin el foco) de una hoja QSS."""
    match = re.search(r"QLineEdit \{.*?\}(?=\s*QLineEdit:focus)", qss, re.S)
    assert match is not None, "la hoja no declara QLineEdit"
    return match.group(0)


@pytest.mark.parametrize("style", ["dark", "comic", "flat", "round"])
def test_inline_input_geometry_matches_design(qapp, style):
    """Borde 2.5px, radio 8px, padding 5px 10px y peso 600 en todos los estilos."""
    from src.gui.styles import styles as s

    bubble = SpeechBubble(style=style)
    qss = bubble.styleSheet()
    block = _input_block(qss)

    assert re.search(r"border\s*:\s*2\.5px solid", block)
    assert re.search(r"border-radius\s*:\s*8px", block)
    assert re.search(r"padding\s*:\s*5px 10px", block)
    assert re.search(r"font-weight\s*:\s*600", block)
    assert re.search(r"font-size\s*:\s*12px", block)
    # El foco usa el token, no un hex suelto.
    assert s.BORDER_FOCUS in qss
    assert re.search(r"QLineEdit:focus \{\s*border-color:", qss)


@pytest.mark.parametrize(
    "style", ["dark", "comic", "flat", "round"],
)
def test_every_style_keeps_its_own_palette(qapp, style):
    """La geometría se homogeneiza, pero cada estilo conserva sus colores."""
    from src.gui.styles import styles as s
    from PySide6.QtGui import QColor

    recipe = s.bubble_style_recipe(style)
    bubble = SpeechBubble(style=style)

    assert bubble._bg_color == QColor(*recipe[0])
    assert bubble._border_color == QColor(*recipe[1])
    assert bubble._border_width == recipe[2]
    assert bubble._radius == recipe[5]

    expected_bg, expected_txt, expected_bdr = s.bubble_input_palette(style)
    block = _input_block(bubble.styleSheet())
    assert re.search(rf"background\s*:\s*{re.escape(expected_bg)}", block)
    assert re.search(rf"color\s*:\s*{re.escape(expected_txt)}", block)
    assert re.search(rf"border\s*:\s*2\.5px solid {re.escape(expected_bdr)}", block)


def test_all_styles_are_visually_distinct(qapp):
    """Los cuatro estilos del combo deben seguir diferenciándose."""
    seen_bg, seen_border = set(), set()
    for style in ("dark", "comic", "flat", "round"):
        bubble = SpeechBubble(style=style)
        seen_bg.add(bubble._bg_color.name())
        seen_border.add(bubble._border_color.name())
    assert len(seen_bg) == 4
    assert len(seen_border) == 4


def test_scrollbar_qss_matches_design(qapp):
    """Design.md §4: scrollbar mínima de 6px con handle redondeado."""
    bubble = SpeechBubble(style="dark")
    qss = bubble.styleSheet()

    assert "QScrollBar:vertical" in qss
    assert re.search(r"QScrollBar:vertical \{[^}]*width\s*:\s*6px", qss, re.S)
    assert re.search(r"background\s*:\s*transparent", qss)
    assert re.search(r"min-height\s*:\s*28px", qss)
    assert re.search(r"border-radius\s*:\s*3px", qss)
    # El handle toma el color del borde de la receta del estilo.
    assert bubble._border_color.name() in qss


def test_radius_never_exceeds_available_space(qapp):
    from src.gui.widgets.speech_bubble import _TAIL_W
    bubble = SpeechBubble(style="round")
    bubble.resize(120, 60)  # narrow: radius must be capped
    path = bubble._build_path()
    assert path is not None


def test_wheel_event_scrolls_content(qapp, qtbot):
    """El QTextEdit es transparente al ratón: la rueda debe reenviarse a él."""
    bubble = SpeechBubble(max_lines=0)  # sin recorte por líneas
    long_text = "\n".join(
        f"linea {i} con texto suficientemente largo" for i in range(40)
    )
    bubble.show_text(long_text, animate=False)
    bubble.show()

    bar = bubble.text_edit.verticalScrollBar()
    qtbot.waitUntil(lambda: bar.maximum() > 0, timeout=2000)
    assert bar.maximum() > 0, "el texto debería desbordar los 150 px máximos"

    before = bar.value()
    QApplication.sendEvent(bubble, _wheel_event(-120))  # rueda hacia abajo
    QTest.qWait(20)
    after_down = bar.value()
    assert after_down > before, "la rueda hacia abajo debe avanzar el contenido"

    QApplication.sendEvent(bubble, _wheel_event(120))   # rueda hacia arriba
    QTest.qWait(20)
    assert bar.value() < after_down
    bubble.hide_bubble()


def test_full_text_kept_for_tooltip(qapp):
    """El recorte afecta solo a lo visible: lo íntegro se recuerda y se puede leer."""
    bubble = SpeechBubble(max_lines=2)
    long_text = "line1\nline2\nline3\nline4"
    bubble.show_text(long_text, animate=False)

    assert bubble._full_text == long_text
    assert "line3" not in bubble.text_edit.toPlainText()
    assert bubble.toolTip() == long_text

    bubble.hide_bubble()
    assert bubble.toolTip() == ""


def test_thinking_uses_i18n(qapp):
    i18n = MagicMock()
    i18n.t = MagicMock(side_effect=lambda key, **kw: "Pensando...")
    bubble = SpeechBubble(i18n=i18n)
    bubble.show_thinking()

    assert bubble.text_edit.toPlainText() == "Pensando..."
    i18n.t.assert_called_with("chat.thinking")
    bubble.hide_bubble()


def test_copy_shortcut(qapp):
    bubble = SpeechBubble()
    bubble.show_text("Texto para copiar", animate=False)
    QTest.qWait(20)

    clipboard = QApplication.clipboard()
    # El portapapeles de Windows es un recurso global: si otro proceso lo
    # tiene tomado, Qt no puede escribir y se reintenta la pulsación real.
    for _ in range(20):
        QTest.keyClick(bubble, Qt.Key_C, Qt.ControlModifier)
        if clipboard.text() == "Texto para copiar":
            break
        QTest.qWait(25)

    assert clipboard.text() == "Texto para copiar"
    bubble.hide_bubble()


def test_set_typewriter_interval_updates_timer(qapp):
    """El intervalo se cambia en caliente (lo empuja el diálogo de Ajustes)."""
    bubble = SpeechBubble(typewriter_interval_ms=30)
    assert bubble._anim_timer.interval() == 30

    bubble.set_typewriter_interval(80)

    assert bubble.typewriter_interval_ms == 80
    assert bubble._anim_timer.interval() == 80
    bubble.hide_bubble()


def test_set_typewriter_interval_applies_while_typing(qapp):
    bubble = SpeechBubble(typewriter_interval_ms=30)
    bubble.show_text("Hola a todos", animate=True)
    QTest.qWait(10)

    bubble.set_typewriter_interval(5)

    assert bubble._anim_timer.isActive()
    assert bubble._anim_timer.interval() == 5
    bubble.hide_bubble()


@pytest.mark.parametrize("bad", [0, -1, -250])
def test_set_typewriter_interval_ignores_non_positive(qapp, bad):
    """Un intervalo <= 0 no debe dejar el QTimer disparando en bucle cerrado."""
    bubble = SpeechBubble(typewriter_interval_ms=30)

    bubble.set_typewriter_interval(bad)  # must not raise

    assert bubble.typewriter_interval_ms == 30
    assert bubble._anim_timer.interval() == 30
