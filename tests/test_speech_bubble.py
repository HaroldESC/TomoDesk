import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.gui.widgets.speech_bubble import SpeechBubble


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
