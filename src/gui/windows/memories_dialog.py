import datetime

from PySide6.QtCore import QLocale, QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSplitter, QTextEdit,
    QVBoxLayout, QWidget,
)

from src.gui.utils import confirm, force_taskbar_entry

#: Estrella de importancia, la misma que ya usaba el listado.
STAR = "\u2605"
#: Rol extra del item donde se guarda el dict completo de la memoria.
MEMORY_ROLE = Qt.ItemDataRole.UserRole + 1
#: Separador de los metadatos de la cabecera del detalle.
SEPARATOR = " \u00b7 "


def _stars(memory: dict) -> str:
    """Estrellas de importancia de una memoria, tolerante a datos sucios.

    ``importance_score`` es un REAL de SQLite y puede venir ``None`` (memoria
    sin puntuar) o texto si el origen escribe mal el valor: en ambos casos se
    trata como 0 estrellas en vez de reventar el diálogo.
    """
    try:
        score = float(memory.get("importance_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    count = int(score * 5)
    return STAR * min(5, max(0, count))


def _ellipsis(text: str, limit: int) -> str:
    """Recorta ``text`` a ``limit`` caracteres anadiendo puntos suspensivos."""
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _format_timestamp(value) -> str:
    """Fecha legible segun el locale del sistema, o el texto original.

    SQLite guarda ``"YYYY-MM-DD HH:MM:SS"``. Si el valor no se puede parsear
    (importaciones antiguas, formatos libres) se devuelve tal cual: es mejor
    una fecha rara que una fecha perdida.
    """
    raw = value if isinstance(value, str) else ("" if value is None else str(value))
    raw = raw.strip()
    if not raw:
        return ""
    try:
        parsed = datetime.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return raw
    return QLocale.system().toString(parsed, QLocale.FormatType.ShortFormat)


class MemoriesDialog(QDialog):
    """Listado de memorias episódicas con panel de lectura y borrado confirmado."""

    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self._memories: list = []
        self.setWindowTitle(self.i18n.t("dialogs.memories.title"))
        self.setMinimumSize(500, 360)
        self.resize(680, 420)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_memories()
        force_taskbar_entry(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.i18n.t("dialogs.memories.saved_memories")))

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.memory_list = QListWidget()
        self.memory_list.setMinimumWidth(260)
        self.memory_list.setAccessibleName(
            self.i18n.t("dialogs.memories.saved_memories")
        )
        self.memory_list.currentItemChanged.connect(self._on_current_changed)
        list_layout.addWidget(self.memory_list, stretch=1)

        self.empty_label = QLabel(self.i18n.t("dialogs.memories.empty"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setVisible(False)
        list_layout.addWidget(self.empty_label, stretch=1)

        self.splitter.addWidget(list_panel)

        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFrameShape(QFrame.Shape.NoFrame)
        # El panel de lectura no debe tragarse el Tab: el recorrido de teclado
        # tiene que poder salir de la vista hacia los botones.
        self.detail_view.setTabChangesFocus(True)
        self.detail_view.setAccessibleName(self.i18n.t("dialogs.memories.title"))
        self.splitter.addWidget(self.detail_view)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([280, 400])

        layout.addWidget(self.splitter, stretch=1)

        btn_layout = QHBoxLayout()

        self.delete_btn = QPushButton(self.i18n.t("dialogs.memories.delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setAccessibleDescription(
            self.i18n.t("dialogs.memories.delete")
        )
        self.delete_btn.setToolTip(self.i18n.t("dialogs.memories.delete_tip"))
        self.delete_btn.clicked.connect(self._delete_memory)
        btn_layout.addWidget(self.delete_btn)

        self.refresh_btn = QPushButton(self.i18n.t("dialogs.memories.refresh"))
        self.refresh_btn.setObjectName("flat")
        self.refresh_btn.clicked.connect(self._load_memories)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

        # Recorrido de Tab natural: listado -> detalle -> botones.
        QWidget.setTabOrder(self.memory_list, self.detail_view)
        QWidget.setTabOrder(self.detail_view, self.delete_btn)
        QWidget.setTabOrder(self.delete_btn, self.refresh_btn)

    def _load_memories(self) -> None:
        """Rellena el listado desde la base de datos y refresca el detalle."""
        memories = self.memory_manager.list_episodic_log() or []
        self._memories = memories

        blocker = QSignalBlocker(self.memory_list)
        self.memory_list.clear()
        for m in memories:
            summary = m.get("summary") or ""
            item = QListWidgetItem(
                self.i18n.t(
                    "commands.memory_item",
                    id=m.get("id"),
                    stars=_stars(m),
                    source=m.get("source") or "",
                    summary=_ellipsis(summary, 70),
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, m.get("id"))
            item.setData(MEMORY_ROLE, m)
            # La lista se queda sin espacio: el tooltip enseña la memoria entera.
            item.setToolTip(summary)
            self.memory_list.addItem(item)
        if memories:
            self.memory_list.setCurrentRow(0)
        del blocker

        self._update_empty_state()
        if self.memory_list.currentItem() is None:
            self._set_detail("")
        else:
            self._show_detail()
        self._update_action_state()

    def _update_empty_state(self) -> None:
        """Muestra el aviso de lista vacía ocultando el listado."""
        empty = self.memory_list.count() == 0
        self.empty_label.setVisible(empty)
        self.memory_list.setVisible(not empty)

    def _update_action_state(self) -> None:
        """Habilita Eliminar solo con una memoria seleccionada.

        Mismo patrón que ``settings_dialog``: el botón gris deja claro que no
        hay nada que borrar en vez de no hacer nada al pulsarlo.
        """
        self.delete_btn.setEnabled(self.memory_list.currentItem() is not None)

    def _on_current_changed(self, current, previous=None) -> None:
        """Puente de ``currentItemChanged`` a :meth:`_show_detail`."""
        self._show_detail()
        self._update_action_state()

    def _show_detail(self) -> None:
        """Pinta la memoria seleccionada en el panel derecho.

        Se usa texto plano a proposito: el resumen es contenido de la base de
        datos y no debe interpretarse como HTML.
        """
        current = self.memory_list.currentItem()
        memory = current.data(MEMORY_ROLE) if current is not None else None
        if not isinstance(memory, dict):
            self._set_detail(self.i18n.t("dialogs.memories.no_selection"))
            return
        header = SEPARATOR.join(
            part for part in (
                _stars(memory),
                memory.get("source") or "",
                _format_timestamp(memory.get("timestamp")),
            )
            if part
        )
        self._set_detail(f"{header}\n\n{memory.get('summary') or ''}")

    def _set_detail(self, text: str) -> None:
        """Escribe ``text`` en el panel de detalle como texto plano."""
        self.detail_view.setPlainText(text)

    def _delete_memory(self) -> None:
        """Borra la memoria seleccionada previa confirmación."""
        current = self.memory_list.currentItem()
        if current is None:
            self._update_action_state()
            return
        if not confirm(
            self,
            self.i18n,
            title_key="dialogs.memories.delete_confirm_title",
            body_key="dialogs.memories.delete_confirm_body",
        ):
            return
        self.memory_manager.delete_episodic_memory(
            current.data(Qt.ItemDataRole.UserRole)
        )
        self._load_memories()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
