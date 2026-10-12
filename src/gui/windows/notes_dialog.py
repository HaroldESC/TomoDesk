from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QTextEdit, QVBoxLayout,
    QWidget,
)

from src.gui.utils import confirm, force_taskbar_entry


class NotesDialog(QDialog):
    """Editor de notas con aviso de cambios sin guardar."""

    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self._notes: list = []
        self._current_row = -1
        self._dirty = False
        self.setWindowTitle(self.i18n.t("dialogs.notes.title"))
        self.setMinimumSize(500, 360)
        self.resize(560, 560)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_notes()
        force_taskbar_entry(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        notes_label = QLabel(self.i18n.t("dialogs.notes.your_notes"))

        self.note_list = QListWidget()
        self.note_list.setMinimumHeight(120)
        self.note_list.setAccessibleName(self.i18n.t("dialogs.notes.your_notes"))
        self.note_list.currentRowChanged.connect(self._on_select)
        notes_label.setBuddy(self.note_list)
        layout.addWidget(notes_label)
        layout.addWidget(self.note_list, stretch=1)

        self.empty_label = QLabel(self.i18n.t("dialogs.notes.empty"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        # El editor necesita poder crecer sin empujar el resto fuera del
        # diálogo: el formulario entero vive en un área desplazable.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        form = QWidget()
        form_layout = QVBoxLayout(form)

        title_label = QLabel(self.i18n.t("dialogs.notes.title_label"))
        self.title_input = QLineEdit()
        title_label.setBuddy(self.title_input)
        form_layout.addWidget(title_label)
        form_layout.addWidget(self.title_input)

        content_label = QLabel(self.i18n.t("dialogs.notes.content_label"))
        self.content_input = QTextEdit()
        self.content_input.setMinimumHeight(160)
        # El editor no debe quedarse con el Tab para sangrar: el recorrido de
        # teclado tiene que poder salir del campo hacia los botones.
        self.content_input.setTabChangesFocus(True)
        self.content_input.setAccessibleName(
            self.i18n.t("dialogs.notes.content_label")
        )
        content_label.setBuddy(self.content_input)
        form_layout.addWidget(content_label)
        form_layout.addWidget(self.content_input)

        self.scroll.setWidget(form)
        layout.addWidget(self.scroll, stretch=1)

        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton(self.i18n.t("dialogs.notes.save"))
        self.save_btn.clicked.connect(self._save_note)
        btn_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton(self.i18n.t("dialogs.notes.delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete_note)
        btn_layout.addWidget(self.delete_btn)

        self.new_btn = QPushButton(self.i18n.t("dialogs.notes.new"))
        self.new_btn.setObjectName("secondary")
        self.new_btn.clicked.connect(self._new_note)
        btn_layout.addWidget(self.new_btn)

        layout.addLayout(btn_layout)

        self.title_input.textChanged.connect(self._mark_dirty)
        self.content_input.textChanged.connect(self._mark_dirty)

        # Recorrido de Tab natural: listado -> editor -> botones.
        QWidget.setTabOrder(self.note_list, self.title_input)
        QWidget.setTabOrder(self.title_input, self.content_input)
        QWidget.setTabOrder(self.content_input, self.save_btn)
        QWidget.setTabOrder(self.save_btn, self.delete_btn)
        QWidget.setTabOrder(self.delete_btn, self.new_btn)

    def _load_notes(self) -> None:
        """Rellena el listado desde la base de datos y recarga el editor."""
        notes = self.memory_manager.list_notes() or []
        self._notes = notes

        blocker = QSignalBlocker(self.note_list)
        self.note_list.clear()
        for note in notes:
            item = QListWidgetItem(
                self.i18n.t(
                    "commands.note_item",
                    id=note.get('id'),
                    title=(note.get('title') or '')[:50],
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, note.get('id'))
            self.note_list.addItem(item)
        row = self._current_row if 0 <= self._current_row < len(notes) else -1
        if row >= 0:
            self.note_list.setCurrentRow(row)
        del blocker

        self._update_empty_state()
        self._select_row(row)

    def _update_empty_state(self) -> None:
        """Muestra el aviso de lista vacía ocultando el listado."""
        empty = self.note_list.count() == 0
        self.empty_label.setVisible(empty)
        self.note_list.setVisible(not empty)

    def _mark_dirty(self) -> None:
        """El usuario ha tocado el editor: hay cambios sin guardar."""
        self._dirty = True

    def _select_row(self, row: int) -> None:
        """Carga la nota de la fila ``row`` en el editor sin preguntar nada."""
        if row < 0 or row >= len(self._notes):
            self._current_row = -1
            self._clear_editor()
            return
        note = self._notes[row]
        title_blocker = QSignalBlocker(self.title_input)
        content_blocker = QSignalBlocker(self.content_input)
        self.title_input.setText(note.get('title') or '')
        self.content_input.setPlainText(note.get('content') or '')
        del title_blocker, content_blocker
        self._current_row = row
        self._dirty = False

    def _clear_editor(self) -> None:
        """Vacía título y contenido sin marcar el diálogo como sucio."""
        title_blocker = QSignalBlocker(self.title_input)
        content_blocker = QSignalBlocker(self.content_input)
        self.title_input.clear()
        self.content_input.clear()
        del title_blocker, content_blocker
        self._dirty = False

    def _restore_current_row(self) -> None:
        """Devuelve la selección de la lista a la nota que se está editando.

        Se bloquean las señales porque el cambio de fila dispararía otra vez
        ``_on_select`` y volvería a preguntar al usuario.
        """
        blocker = QSignalBlocker(self.note_list)
        self.note_list.setCurrentRow(self._current_row)
        del blocker

    def _confirm_discard(self) -> bool:
        """True si se puede seguir; False si el usuario quiere seguir editando."""
        if not self._dirty:
            return True
        return confirm(
            self,
            self.i18n,
            title_key="dialogs.notes.unsaved_title",
            body_key="dialogs.notes.unsaved_body",
        )

    def _on_select(self, row: int) -> None:
        """Cambia de nota; si hay cambios sin guardar, pregunta antes."""
        if row == self._current_row:
            return
        if not self._confirm_discard():
            self._restore_current_row()
            return
        self._select_row(row)

    def _save_note(self) -> None:
        """Guarda la nota editada (o la crea si no hay ninguna seleccionada)."""
        title = self.title_input.text().strip()
        content = self.content_input.toPlainText().strip()
        if not title:
            return

        current_row = self.note_list.currentRow()
        if current_row >= 0 and current_row < len(self._notes):
            note_id = self._notes[current_row]['id']
            self.memory_manager.update_note(note_id, title=title, content=content)
            saved_row = current_row
        else:
            self.memory_manager.add_note(title, content)
            # ``list_notes`` ordena por id DESC: la nota nueva va primera.
            saved_row = 0 if self._notes else -1

        self._current_row = saved_row
        self._load_notes()

    def _delete_note(self) -> None:
        """Borra la nota seleccionada previa confirmación.

        No se pide confirmación por los cambios sin guardar: al borrar la nota
        esos cambios se descartan de todos modos, así que basta con una sola
        pregunta (la de borrado).
        """
        current_row = self.note_list.currentRow()
        if current_row < 0 or current_row >= len(self._notes):
            return
        if not confirm(
            self,
            self.i18n,
            title_key="dialogs.notes.delete_confirm_title",
            body_key="dialogs.notes.delete_confirm_body",
        ):
            return
        note_id = self._notes[current_row]['id']
        self.memory_manager.delete_note(note_id)
        self._current_row = -1
        self._load_notes()
        self._clear_editor()

    def _new_note(self) -> None:
        """Prepara una nota en blanco, avisando de los cambios pendientes."""
        if not self._confirm_discard():
            self._restore_current_row()
            return
        blocker = QSignalBlocker(self.note_list)
        # clearSelection() no mueve la fila actual: hay que deseleccionar de
        # verdad o "guardar" seguiría actualizando la nota anterior.
        self.note_list.setCurrentRow(-1)
        del blocker
        self._current_row = -1
        self._clear_editor()
        self.title_input.setFocus()

    def closeEvent(self, event) -> None:
        """Cerrar con cambios sin guardar pide confirmación (botón X)."""
        if not self._confirm_discard():
            event.ignore()
            return
        # QDialog.closeEvent() llama a reject(), que preguntaría otra vez.
        self._dirty = False
        super().closeEvent(event)

    def reject(self) -> None:
        """La tecla Esc no pasa por closeEvent (QDialog llama a reject())."""
        if not self._confirm_discard():
            return
        self._dirty = False
        super().reject()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
