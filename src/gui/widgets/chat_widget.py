from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
)

from src.gui.styles.styles import (
    ACCENT_LIGHT, BG_SURFACE, BORDER, BG_SYSTEM_MSG, TEXT_SECONDARY, TEXT_PRIMARY,
    ACCENT_LIGHT_DK, BG_SURFACE_DK, BORDER_DK, BG_SYSTEM_MSG_DK, TEXT_SECONDARY_DK, TEXT_PRIMARY_DK,
)

_USER_BG  = ACCENT_LIGHT
_ASST_BG  = BG_SURFACE
_ASST_BDR = BORDER
_SYS_BG   = BG_SYSTEM_MSG
_SYS_TEXT = TEXT_SECONDARY
_TEXT     = TEXT_PRIMARY

_USER_BG_DK  = ACCENT_LIGHT_DK
_ASST_BG_DK  = BG_SURFACE_DK
_ASST_BDR_DK = BORDER_DK
_SYS_BG_DK   = BG_SYSTEM_MSG_DK
_SYS_TEXT_DK = TEXT_SECONDARY_DK
_TEXT_DK     = TEXT_PRIMARY_DK

_FONT                 = "Segoe UI, Inter, Arial"
_MAX_BUBBLE_WIDTH_RATIO = 0.72
# Tolerancia (px) para considerar que el usuario sigue "pegado" al fondo.
_SCROLL_BOTTOM_TOLERANCE = 4


class MessageBubble(QFrame):
    """
    A single chat message bubble backed by QLabel.

    QLabel with setWordWrap(True) asks Qt's layout engine to size the widget,
    so there is no manual height calculation, no QTimer, and no risk of the
    bubble being too tall or too short.
    """

    def __init__(self, text: str, role: str, theme: str = "light", parent=None):
        super().__init__(parent)
        self._role  = role
        self._theme = theme

        v_pad = 4 if role == "system" else 8

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, v_pad, 14, v_pad)
        layout.setSpacing(0)

        self.label = QLabel(text)
        self.label.setWordWrap(True)
        # Qt habilita el menú contextual nativo (Select All / Copy) y la
        # navegación por teclado, de modo que el texto ya se puede copiar.
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        )
        # Accesibilidad: un lector de pantalla anuncia el rol y un extracto.
        self.label.setAccessibleName(role)
        self.label.setAccessibleDescription(text[:80])
        # Let the label shrink horizontally (the parent constrains width).
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        layout.addWidget(self.label)

        # The bubble itself should never grow taller than its content needs.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self._apply_theme(theme)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _palette(self, theme: str) -> dict:
        pal = {
            "light": {
                "user":      {"bg": _USER_BG,     "text": _TEXT,     "border": ""},
                "assistant": {"bg": _ASST_BG,     "text": _TEXT,     "border": f"border: 1px solid {_ASST_BDR};"},
                "system":    {"bg": _SYS_BG,      "text": _SYS_TEXT, "border": ""},
            },
            "dark": {
                "user":      {"bg": _USER_BG_DK,  "text": _TEXT_DK,     "border": ""},
                "assistant": {"bg": _ASST_BG_DK,  "text": _TEXT_DK,     "border": f"border: 1px solid {_ASST_BDR_DK};"},
                "system":    {"bg": _SYS_BG_DK,   "text": _SYS_TEXT_DK, "border": ""},
            },
        }
        return pal.get(theme, pal["light"]).get(self._role, pal["light"]["system"])

    _RADII = {
        "user":      "12px 12px 4px 12px",
        "assistant": "12px 12px 12px 4px",
        "system":    "8px",
    }

    def _apply_theme(self, theme: str):
        c      = self._palette(theme)
        radii  = self._RADII.get(self._role, "8px")

        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {c["bg"]};
                {c["border"]}
                border-radius: {radii};
            }}
        """)
        self.label.setStyleSheet(
            f"color: {c['text']}; background: transparent; border: none; "
            f"font-family: {_FONT}; font-size: 13px;"
        )

    def set_theme(self, theme: str):
        self._theme = theme
        self._apply_theme(theme)


class ChatWidget(QWidget):
    """
    Scrollable chat log.

    Each message is added as a MessageBubble wrapped in a QHBoxLayout row
    so that horizontal alignment (left / right / center) works correctly
    regardless of Qt version.
    """

    def __init__(self, parent=None, i18n=None, theme: str = "light"):
        super().__init__(parent)
        self.i18n  = i18n
        self.theme = theme

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")

        self.message_container = QWidget()
        self.message_container.setStyleSheet("background: transparent;")
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(0, 0, 0, 0)
        self.message_layout.setSpacing(4)
        self.message_layout.addStretch()   # pushes messages upward initially

        self.scroll_area.setWidget(self.message_container)
        root.addWidget(self.scroll_area)

        # Flag "stick to bottom": el usuario está leyendo el final del
        # historial, así que cada recálculo del rango debe dejarnos abajo.
        # insertWidget solo invalida el layout, por lo que el rango de la
        # scrollbar llega después (LayoutRequest) y el scroll se reintenta
        # desde _on_range_changed.
        self._stick_to_bottom = False
        self.scroll_area.verticalScrollBar().rangeChanged.connect(
            self._on_range_changed
        )

        self._apply_theme_style(theme)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str):
        # Se decide ANTES de insertar: insertWidget solo invalida el layout y
        # encola un QEvent::LayoutRequest, así que el rango de la scrollbar
        # todavía no refleja el mensaje nuevo.
        was_at_bottom = self._is_at_bottom()

        bubble = MessageBubble(content, role, theme=self.theme)
        bubble.setMaximumWidth(self._bubble_max_width())

        # Wrap the bubble in a row widget so alignment is handled by a real
        # horizontal layout, not by Qt's layout alignment flag (unreliable
        # for QFrame children in a QVBoxLayout across Qt versions).
        row        = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        if role == "user":
            row_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
            row_layout.addWidget(bubble)
        elif role == "assistant":
            row_layout.addWidget(bubble)
            row_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        else:  # system — centered
            row_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
            row_layout.addWidget(bubble)
            row_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Insert before the trailing stretch item.
        self.message_layout.insertWidget(self.message_layout.count() - 1, row)

        if was_at_bottom:
            # Se aplaza al bucle de eventos y se mantiene el flag hasta que el
            # layout recalcule de verdad el rango de la scrollbar.
            self._stick_to_bottom = True
            QTimer.singleShot(0, self._scroll_to_bottom)
        else:
            # El usuario estaba leyendo más arriba: NO se le arrastra, se
            # conserva su posición de lectura.
            self._stick_to_bottom = False

    def set_theme(self, theme: str):
        self.theme = theme
        self._apply_theme_style(theme)
        for i in range(self.message_layout.count()):
            row_item = self.message_layout.itemAt(i)
            if row_item is None:
                continue
            row_widget = row_item.widget()
            if row_widget is None:
                continue
            row_layout = row_widget.layout()
            if row_layout is None:
                continue
            for j in range(row_layout.count()):
                child = row_layout.itemAt(j)
                if child and isinstance(child.widget(), MessageBubble):
                    child.widget().set_theme(theme)

    def toPlainText(self) -> str:
        texts = []
        for i in range(self.message_layout.count()):
            row_item = self.message_layout.itemAt(i)
            if row_item is None:
                continue
            row_widget = row_item.widget()
            if row_widget is None:
                continue
            row_layout = row_widget.layout()
            if row_layout is None:
                continue
            for j in range(row_layout.count()):
                child = row_layout.itemAt(j)
                if child and isinstance(child.widget(), MessageBubble):
                    texts.append(child.widget().label.text())
        return "\n".join(texts)

    def clear(self):
        self._stick_to_bottom = False
        # Remove every row except the trailing stretch item.
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bubble_max_width(self) -> int:
        w = self.width()
        # Fall back to a reasonable default until the widget has been shown
        # and has a real width from the layout engine.
        if w <= 0:
            w = 400
        return max(280, int(w * _MAX_BUBBLE_WIDTH_RATIO))

    def _apply_theme_style(self, theme: str):
        chat_bg     = "#0F0F1A" if theme == "dark" else "#F5F5FA"
        chat_border = "#282848" if theme == "dark" else "#D4D4EC"
        self.setStyleSheet(f"""
            ChatWidget {{
                background-color: {chat_bg};
                border: 1.5px solid {chat_border};
                border-radius: 12px;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)

    def _is_at_bottom(self) -> bool:
        """Indica si la vista está pegada al final del historial."""
        try:
            sb = self.scroll_area.verticalScrollBar()
            return sb.value() >= sb.maximum() - _SCROLL_BOTTOM_TOLERANCE
        except RuntimeError:
            return False

    def _on_range_changed(self, _minimum: int, _maximum: int):
        """
        El layout acaba de recalcular el rango real de la scrollbar.

        Es el punto fiable para fijar el fondo: cuando insertWidget encola el
        LayoutRequest, maximum() todavía era el valor obsoleto. El scroll se
        aplaza un turno más porque dentro de rangeChanged la scrollbar está a
        medio actualizar.
        """
        if self._stick_to_bottom:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        try:
            sb = self.scroll_area.verticalScrollBar()
            sb.setValue(sb.maximum())
            # Si el contenido cabe entero no hay nada a lo que pegarse: el flag
            # se conserva por si el rango crece después.
            if sb.maximum() > 0:
                self._stick_to_bottom = False
        except RuntimeError:
            pass

    def resizeEvent(self, event):
        # Si el chat estaba pegado al fondo, el nuevo ancho (y por tanto el
        # nuevo alto del contenido) debe volver a dejarnos al fondo.
        was_at_bottom = self._is_at_bottom()
        self._stick_to_bottom = was_at_bottom
        super().resizeEvent(event)
        max_w = self._bubble_max_width()
        # Update every bubble's maximum width so text re-wraps correctly.
        for i in range(self.message_layout.count()):
            row_item = self.message_layout.itemAt(i)
            if row_item is None:
                continue
            row_widget = row_item.widget()
            if row_widget is None:
                continue
            row_layout = row_widget.layout()
            if row_layout is None:
                continue
            for j in range(row_layout.count()):
                child = row_layout.itemAt(j)
                if child and isinstance(child.widget(), MessageBubble):
                    child.widget().setMaximumWidth(max_w)

        if was_at_bottom:
            # Aplazado: el ancho de las burbujas aún no ha reconfigurado el
            # layout, así que maximum() está obsoleto en este instante.
            self._stick_to_bottom = True
            QTimer.singleShot(0, self._scroll_to_bottom)
