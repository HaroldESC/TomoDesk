import logging
from enum import Enum

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLineEdit, QTextEdit, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_TAIL_H = 13
_TAIL_W = 20

_MIN_BUBBLE_WIDTH = 150
_MAX_BUBBLE_WIDTH = 450
_MAX_CONTENT_HEIGHT = 150


class BubbleStyle(Enum):
    DARK  = "dark"
    COMIC = "comic"


class SpeechBubble(QWidget):
    clicked = Signal()
    message_sent = Signal(str)
    double_clicked = Signal()
    resized = Signal()
    typewriter_finished = Signal()

    def __init__(self, parent=None, style: str = "dark", max_width: int = _MAX_BUBBLE_WIDTH,
                 max_lines: int = 5, fade_delay_ms: int = 4000,
                 typewriter_interval_ms: int = 30, i18n=None):
        super().__init__(parent)
        self.style = BubbleStyle(style)
        self._drag_pos = None
        self._drag_active = False
        self._full_text = ""
        self._anim_index = 0
        self.max_lines = max_lines
        self.fade_delay_ms = fade_delay_ms
        self.typewriter_interval_ms = typewriter_interval_ms
        self.i18n = i18n
        self._base_max_width = max_width

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(_MIN_BUBBLE_WIDTH)
        self._update_max_width()

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 8 + _TAIL_H)
        self._layout.setSpacing(4)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text_edit.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setFrameStyle(0)
        self.text_edit.setContentsMargins(0, 0, 0, 0)
        self.text_edit.document().setDocumentMargin(0)
        self.text_edit.setStyleSheet("QScrollBar:vertical { width: 0px; background: transparent; }"
                                     "QScrollBar::handle:vertical { background: transparent; }"
                                     "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")
        self._layout.addWidget(self.text_edit)

        self.input_edit = QLineEdit(self)
        self.input_edit.setVisible(False)
        placeholder = self.i18n.t("interaction.inline_placeholder") if self.i18n else "Type a message..."
        self.input_edit.setPlaceholderText(placeholder)
        self.input_edit.returnPressed.connect(self._send_inline_message)
        self.input_edit.installEventFilter(self)
        self._layout.addWidget(self.input_edit)

        self._flipped = False
        self._bg_color     = QColor(30, 30, 46)
        self._border_color = QColor(49, 50, 68)
        self._border_width = 1.5
        self._apply_style()
        self._update_margins()

        self._resize_pending = False
        self.text_edit.document().contentsChanged.connect(self._schedule_resize)

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(self.typewriter_interval_ms)
        self._anim_timer.timeout.connect(self._on_anim_tick)

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self.hide_bubble)

    def _update_max_width(self):
        screen = QGuiApplication.primaryScreen()
        screen_w = screen.geometry().width() if screen else 1920
        dynamic_max = min(self._base_max_width, int(screen_w * 0.30))
        self.setMaximumWidth(dynamic_max)

    def _apply_style(self):
        if self.style == BubbleStyle.DARK:
            self._bg_color     = QColor(30, 30, 46)
            self._border_color = QColor(49, 50, 68)
            self._border_width = 1.5
            text_color   = "#cdd6f4"
            font_weight  = "400"
        else:
            self._bg_color     = QColor(255, 255, 255)
            self._border_color = QColor(30, 30, 48)
            self._border_width = 2.5
            text_color   = "#1E1E30"
            font_weight  = "600"

        input_bg   = "#2B2B3D" if self.style == BubbleStyle.DARK else "#F0F0F8"
        input_txt  = "#cdd6f4" if self.style == BubbleStyle.DARK else "#1E1E30"
        input_bdr  = "#494A44" if self.style == BubbleStyle.DARK else "#1E1E30"

        self.setStyleSheet(f"""
            QTextEdit {{
                background : transparent;
                border     : none;
                padding    : 0px;
                margin     : 0px;
                color      : {text_color};
                font-size  : 13px;
                font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
                font-weight: {font_weight};
                line-height: 1.4;
            }}
            QScrollBar:vertical {{
                width      : 0px;
                background : transparent;
            }}
            QScrollBar::handle:vertical {{
                background : transparent;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height : 0px;
            }}
            QLineEdit {{
                background : {input_bg};
                color      : {input_txt};
                border     : 1.5px solid {input_bdr};
                border-radius: 6px;
                padding    : 4px 8px;
                font-size  : 12px;
                font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
            }}
            QLineEdit:focus {{
                border-color: #7B85D6;
            }}
        """)
        self.update()

    def _update_margins(self):
        if self._flipped:
            self._layout.setContentsMargins(12, 8 + _TAIL_H, 12, 8)
        else:
            self._layout.setContentsMargins(12, 8, 12, 8 + _TAIL_H)

    def set_flipped(self, flipped: bool):
        if self._flipped != flipped:
            self._flipped = flipped
            self._update_margins()
            self.update()

    def adjustSize(self):
        self._update_max_width()
        doc = self.text_edit.document()
        max_w = self.maximumWidth()

        doc.setTextWidth(-1)
        natural_w = doc.idealWidth()

        target_w = max(self.minimumWidth(), min(int(natural_w), max_w))

        doc.setTextWidth(target_w - 24)

        doc_h = doc.size().height()

        if doc_h > _MAX_CONTENT_HEIGHT:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            doc_h = _MAX_CONTENT_HEIGHT
        else:
            self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        input_h = self.input_edit.sizeHint().height() if self.input_edit.isVisible() else 0
        widget_h = int(doc_h + 16 + _TAIL_H + input_h + (4 if input_h else 0))

        self.resize(target_w, max(40, widget_h))

    def _build_path(self) -> QPainterPath:
        w  = float(self.width())
        h  = float(self.height())
        r  = 12.0
        cx = w / 2.0

        path = QPainterPath()
        if self._flipped:
            body_top = _TAIL_H
            path.moveTo(r, body_top)
            path.lineTo(cx - _TAIL_W / 2, body_top)
            path.lineTo(cx, 0)
            path.lineTo(cx + _TAIL_W / 2, body_top)
            path.lineTo(w - r, body_top)
            path.quadTo(w, body_top, w, body_top + r)
            path.lineTo(w, h - r)
            path.quadTo(w, h, w - r, h)
            path.lineTo(r, h)
            path.quadTo(0, h, 0, h - r)
            path.lineTo(0, body_top + r)
            path.quadTo(0, body_top, r, body_top)
        else:
            body_y = h - _TAIL_H
            path.moveTo(r, 0)
            path.lineTo(w - r, 0)
            path.quadTo(w, 0, w, r)
            path.lineTo(w, body_y - r)
            path.quadTo(w, body_y, w - r, body_y)
            path.lineTo(cx + _TAIL_W / 2, body_y)
            path.lineTo(cx, h)
            path.lineTo(cx - _TAIL_W / 2, body_y)
            path.lineTo(r, body_y)
            path.quadTo(0, body_y, 0, body_y - r)
            path.lineTo(0, r)
            path.quadTo(0, 0, r, 0)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = self._build_path()
        painter.fillPath(path, QBrush(self._bg_color))
        pen = QPen(self._border_color, self._border_width)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.drawPath(path)
        super().paintEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def _schedule_resize(self):
        if not self._resize_pending:
            self._resize_pending = True
            QTimer.singleShot(0, self._do_resize)

    def _do_resize(self):
        self._resize_pending = False
        self.adjustSize()

    @staticmethod
    def _reading_time_ms(text: str, base_ms: int = 4000) -> int:
        if not text:
            return base_ms
        words = len(text.split())
        per_word = 300
        return min(max(words * per_word, base_ms), 30000)

    def _start_fade_timer(self, text: str):
        if self.fade_delay_ms > 0:
            delay = self._reading_time_ms(text, self.fade_delay_ms)
            self._fade_timer.start(delay)

    def show_text(self, text: str, animate: bool = False):
        self._fade_timer.stop()
        self._anim_timer.stop()

        if self.max_lines and self.max_lines > 0:
            lines = text.split("\n")
            if len(lines) > self.max_lines:
                text = "\n".join(lines[:self.max_lines]) + "\n..."

        self._full_text = text
        if animate and text:
            self._anim_index = 0
            self.text_edit.setPlainText("")
            self._anim_timer.start()
        else:
            self.text_edit.setPlainText(text)
            self._start_fade_timer(text)
        self.show()

    def show_thinking(self):
        self._fade_timer.stop()
        self._anim_timer.stop()
        self.text_edit.setPlainText("...")
        self.show()

        if self.fade_delay_ms > 0:
            self._fade_timer.start(self.fade_delay_ms)

    def hide_bubble(self):
        self._fade_timer.stop()
        self._anim_timer.stop()
        self.hide_inline_input()
        self.hide()
        self.text_edit.clear()

    def set_style(self, style: str):
        try:
            self.style = BubbleStyle(style)
            self._apply_style()
        except ValueError:
            logger.warning("Unknown bubble style: %r", style)

    def show_inline_input(self):
        self._fade_timer.stop()
        self.input_edit.show()
        self.input_edit.setFocus()
        self.adjustSize()

    def hide_inline_input(self):
        self.input_edit.hide()
        self.input_edit.clear()
        self.adjustSize()

    def toggle_inline_input(self):
        if self.input_edit.isVisible():
            self.hide_inline_input()
        else:
            self.show_inline_input()

    def _send_inline_message(self):
        text = self.input_edit.text().strip()
        if text:
            self.message_sent.emit(text)
        self.hide_inline_input()

    def _on_anim_tick(self):
        self._anim_index += 1
        if self._anim_index <= len(self._full_text):
            self.text_edit.setPlainText(self._full_text[:self._anim_index])
        else:
            self._anim_timer.stop()
            self._start_fade_timer(self._full_text)
            self.typewriter_finished.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._drag_active = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self._drag_active = True
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_pos is not None:
            delta = (event.globalPosition().toPoint() - self._drag_pos).manhattanLength()
            if delta < 5:
                self.clicked.emit()
        self._drag_pos = None
        self._drag_active = False
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide_inline_input()
                return True
        return super().eventFilter(obj, event)
