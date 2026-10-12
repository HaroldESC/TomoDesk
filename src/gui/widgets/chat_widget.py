import datetime

from PySide6.QtCore import QDate, QLocale, Qt, QTime, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
)

from src.gui.styles.styles import (
    chat_bubble_frame_qss, chat_bubble_label_qss, chat_frame_qss,
)

_MAX_BUBBLE_WIDTH_RATIO = 0.72
# Tolerancia (px) para considerar que el usuario sigue "pegado" al fondo.
_SCROLL_BOTTOM_TOLERANCE = 4
# Cadencia de la animacion de "escribiendo..." (ms).
_TYPING_INTERVAL_MS = 400
# Ciclo de la burbuja de "escribiendo...".
_TYPING_FRAMES = ("", ".", "..", "...")


def _format_time(moment: datetime.datetime) -> str:
    """Hora (HH:MM) segun el locale del sistema."""
    return QLocale.system().toString(
        QTime(moment.hour, moment.minute), QLocale.ShortFormat
    )


def _format_date(day: datetime.date) -> str:
    """Fecha corta segun el locale del sistema."""
    return QLocale.system().toString(
        QDate(day.year, day.month, day.day), QLocale.ShortFormat
    )


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

    def _apply_theme(self, theme: str):
        """Aplica las hojas de burbuja de ``styles`` (Design.md §2.3)."""
        self.setStyleSheet(chat_bubble_frame_qss(self._role, theme))
        self.label.setStyleSheet(chat_bubble_label_qss(self._role, theme))

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
        # Rango vigente cuando se enciende el flag: el layout aún puede
        # estar por recalcular, así que no basta con mirar ``maximum()``.
        self._stick_range: tuple[int, int] | None = None
        self.scroll_area.verticalScrollBar().rangeChanged.connect(
            self._on_range_changed
        )

        # Indicador de "escribiendo...": una sola burbuja y un solo timer
        # (hijo del widget) viven mientras dure la respuesta.
        self._typing_row: QWidget | None = None
        self._typing_bubble: MessageBubble | None = None
        self._typing_step = 0
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(_TYPING_INTERVAL_MS)
        self._typing_timer.timeout.connect(self._animate_typing)

        # Dia del ultimo mensaje real: decide el separador de cabecera.
        self._last_day: datetime.date | None = None

        self._apply_theme_style(theme)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_message(
        self,
        role: str,
        content: str,
        timestamp: datetime.datetime | None = None,
    ) -> None:
        """Añade una burbuja al registro.

        La hora **no** se pinta bajo la burbuja (ensuciaria el diseño,
        ``Design.md`` §2.3): va en su tooltip, formateada con el locale del
        sistema (hora si es de hoy, "Ayer HH:MM" si es de ayer, fecha y hora
        si es de otro dia). Cuando el dia cambia se inserta antes un
        separador, como mucho uno por cambio.
        """
        moment = timestamp or datetime.datetime.now()
        self._insert_day_separator(moment.date())
        self._add_row(role, content, timestamp=moment)
        self._last_day = moment.date()

    def set_typing(self, active: bool) -> None:
        """Muestra u oculta la burbuja de "escribiendo...".

        Es idempotente: llamar dos veces con el mismo valor no duplica la
        burbuja. Al desactivarla el temporizador queda parado.
        """
        if not active:
            self._remove_typing_bubble()
            return
        if self._typing_row is not None:
            return
        self._typing_step = 0
        row = self._add_row("assistant", _TYPING_FRAMES[0])
        bubble = self._row_bubble(row)
        if bubble is None:  # pragma: no cover - la fila siempre trae burbuja
            return
        bubble.setProperty("_typing", True)
        self._typing_row = row
        self._typing_bubble = bubble
        self._typing_timer.start()

    @property
    def is_typing(self) -> bool:
        """``True`` mientras la burbuja de "escribiendo..." esté en pantalla."""
        return self._typing_row is not None

    def set_theme(self, theme: str):
        self.theme = theme
        self._apply_theme_style(theme)
        for bubble in self._iter_bubbles():
            bubble.set_theme(theme)

    def toPlainText(self) -> str:
        """Historial visible.

        Los separadores de dia y la burbuja de "escribiendo..." no son
        mensajes: quedan marcados con ``_separator`` / ``_typing`` y se saltan.
        """
        return "\n".join(
            bubble.label.text()
            for bubble in self._iter_bubbles()
            if not self._is_auxiliary(bubble)
        )

    def clear(self):
        self._stick_to_bottom = False
        self._stick_range = None
        self._last_day = None
        self._typing_row = None
        self._typing_bubble = None
        self._typing_step = 0
        self._typing_timer.stop()
        # Remove every row except the trailing stretch item.
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_row(
        self,
        role: str,
        text: str,
        timestamp: datetime.datetime | None = None,
        separator: bool = False,
    ) -> QWidget:
        """Construye e inserta una fila (burbuja + alineacion) en el registro.

        La comparten ``add_message``, el separador de dia y el indicador de
        "escribiendo...", de modo que los tres respetan el pegado al fondo.
        Devuelve el widget de la fila.
        """
        # Se decide ANTES de insertar: insertWidget solo invalida el layout y
        # encola un QEvent::LayoutRequest, así que el rango de la scrollbar
        # todavía no refleja la fila nueva.
        was_at_bottom = self._is_at_bottom()

        bubble = MessageBubble(text, role, theme=self.theme)
        bubble.setMaximumWidth(self._bubble_max_width())
        if separator:
            # Marca: no es historial de texto, solo una cabecera de dia.
            bubble.setProperty("_separator", True)
        elif timestamp is not None:
            bubble.setToolTip(self._timestamp_tooltip(timestamp))

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
            self._arm_stick_to_bottom()
        else:
            # El usuario estaba leyendo más arriba: NO se le arrastra, se
            # conserva su posición de lectura.
            self._stick_to_bottom = False
            self._stick_range = None

        return row

    def _iter_bubbles(self):
        """Recorre las burbujas del registro en orden de insercion."""
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
                bubble = row_layout.itemAt(j).widget()
                if isinstance(bubble, MessageBubble):
                    yield bubble

    @staticmethod
    def _row_bubble(row: QWidget) -> MessageBubble | None:
        """Burbuja que hay dentro de una fila de mensaje."""
        row_layout = row.layout() if row is not None else None
        if row_layout is None:
            return None
        for j in range(row_layout.count()):
            bubble = row_layout.itemAt(j).widget()
            if isinstance(bubble, MessageBubble):
                return bubble
        return None

    @staticmethod
    def _is_auxiliary(bubble: MessageBubble) -> bool:
        """``True`` en separadores de dia y en la burbuja de escribiendo."""
        return bool(bubble.property("_separator")) or bool(
            bubble.property("_typing")
        )

    def _bubble_max_width(self) -> int:
        w = self.width()
        # Fall back to a reasonable default until the widget has been shown
        # and has a real width from the layout engine.
        if w <= 0:
            w = 400
        return max(280, int(w * _MAX_BUBBLE_WIDTH_RATIO))

    def _apply_theme_style(self, theme: str):
        """Marco del chat: hoja única en ``styles`` (Design.md §5.1)."""
        self.setStyleSheet(chat_frame_qss(theme))

    def _t(self, key: str, default: str, **kwargs) -> str:
        """``i18n.t`` tolerante a un chat construido sin gestor de idioma."""
        if self.i18n is None:
            try:
                return default.format(**kwargs)
            except (KeyError, IndexError):  # pragma: no cover - defensive
                return default
        return self.i18n.t(key, **kwargs)

    def _timestamp_tooltip(self, moment: datetime.datetime) -> str:
        """Hora hoy, "Ayer HH:MM" ayer y fecha+hora para dias anteriores."""
        time_text = _format_time(moment)
        today = datetime.date.today()
        if moment.date() == today:
            return time_text
        if moment.date() == today - datetime.timedelta(days=1):
            return self._t(
                "chat.timestamp_yesterday", "Yesterday {time}", time=time_text
            )
        return self._t(
            "chat.timestamp_past", "{date} {time}",
            date=_format_date(moment.date()), time=time_text,
        )

    def _insert_day_separator(self, day: datetime.date) -> None:
        """Cabecera "Hoy"/"Ayer"/fecha: una sola por cambio de dia."""
        if self._last_day is None or day == self._last_day:
            return
        self._add_row("system", self._day_separator_text(day), separator=True)

    def _day_separator_text(self, day: datetime.date) -> str:
        today = datetime.date.today()
        if day == today:
            return self._t("chat.day_today", "Today")
        if day == today - datetime.timedelta(days=1):
            return self._t("chat.day_yesterday", "Yesterday")
        return self._t(
            "chat.day_separator", "{date}", date=_format_date(day)
        )

    def _animate_typing(self) -> None:
        """Avanza el ciclo "" -> "." -> ".." -> "..." de "escribiendo..."."""
        if self._typing_bubble is None:
            self._typing_timer.stop()
            return
        self._typing_step = (self._typing_step + 1) % len(_TYPING_FRAMES)
        self._typing_bubble.label.setText(_TYPING_FRAMES[self._typing_step])

    def _remove_typing_bubble(self) -> None:
        """Quita la burbuja de escribiendo y deja el timer parado."""
        self._typing_timer.stop()
        self._typing_step = 0
        row = self._typing_row
        self._typing_row = None
        self._typing_bubble = None
        if row is None:
            return

        was_at_bottom = self._is_at_bottom()
        index = self.message_layout.indexOf(row)
        if index >= 0:
            item = self.message_layout.takeAt(index)
            if item.widget():
                item.widget().deleteLater()
        # El contenido encoge: si estaba al fondo, vuelve a él.
        if was_at_bottom:
            self._arm_stick_to_bottom()
        else:
            self._stick_to_bottom = False
            self._stick_range = None

    def _is_at_bottom(self) -> bool:
        """Indica si la vista está pegada al final del historial."""
        try:
            sb = self.scroll_area.verticalScrollBar()
            return sb.value() >= sb.maximum() - _SCROLL_BOTTOM_TOLERANCE
        except RuntimeError:
            return False

    def _arm_stick_to_bottom(self) -> None:
        """Enciende el flag guardando el rango vigente.

        El flag solo se calma cuando el layout recalcula de verdad el rango:
        si el historial ya estaba desbordado, ``maximum()`` sigue siendo el
        valor viejo y el ``rangeChanged`` posterior se encontraria sin flag.
        """
        sb = self.scroll_area.verticalScrollBar()
        self._stick_range = (sb.minimum(), sb.maximum())
        self._stick_to_bottom = True
        QTimer.singleShot(0, self._scroll_to_bottom)

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
            current = (sb.minimum(), sb.maximum())
            if self._stick_range is None or current != self._stick_range:
                # Rango ya recalculado: el flag puede calmarse.
                self._stick_to_bottom = False
            # Si el rango sigue siendo el que se vio al armar el flag, el
            # LayoutRequest sigue en cola: el flag se conserva para que el
            # rangeChanged posterior vuelva a pegarnos al fondo.
        except RuntimeError:
            pass

    def resizeEvent(self, event):
        # Si el chat estaba pegado al fondo, el nuevo ancho (y por tanto el
        # nuevo alto del contenido) debe volver a dejarnos al fondo.
        was_at_bottom = self._is_at_bottom()
        if was_at_bottom:
            self._arm_stick_to_bottom()
        else:
            self._stick_to_bottom = False
            self._stick_range = None
        super().resizeEvent(event)
        max_w = self._bubble_max_width()
        # Update every bubble's maximum width so text re-wraps correctly.
        for bubble in self._iter_bubbles():
            bubble.setMaximumWidth(max_w)