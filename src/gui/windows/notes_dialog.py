import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout,
)

if sys.platform == "win32":
    _WS_EX_APPWINDOW = 0x00040000
    _GWL_EXSTYLE = -20


def _force_taskbar_entry(widget):
    if sys.platform != "win32":
        return
    widget.winId()
    hwnd = int(widget.winId())
    current = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, current | _WS_EX_APPWINDOW)


class NotesDialog(QDialog):
    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self.setWindowTitle(self.i18n.t("dialogs.notes.title"))
        self.setMinimumSize(500, 360)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_notes()
        _force_taskbar_entry(self)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.note_list = QListWidget()
        self.note_list.currentRowChanged.connect(self._on_select)
        layout.addWidget(QLabel(self.i18n.t("dialogs.notes.your_notes")))
        layout.addWidget(self.note_list)

        layout.addWidget(QLabel(self.i18n.t("dialogs.notes.title_label")))
        self.title_input = QLineEdit()
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel(self.i18n.t("dialogs.notes.content_label")))
        self.content_input = QTextEdit()
        self.content_input.setMaximumHeight(100)
        layout.addWidget(self.content_input)

        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton(self.i18n.t("dialogs.notes.save"))
        self.save_btn.clicked.connect(self._save_note)
        btn_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton(self.i18n.t("dialogs.notes.delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete_note)
        btn_layout.addWidget(self.delete_btn)

        self.new_btn = QPushButton(self.i18n.t("dialogs.notes.new"))
        self.new_btn.clicked.connect(self._new_note)
        btn_layout.addWidget(self.new_btn)

        layout.addLayout(btn_layout)

    def _load_notes(self):
        self.note_list.clear()
        notes = self.memory_manager.list_notes()
        self._notes = notes
        for note in notes:
            item = QListWidgetItem(self.i18n.t("commands.note_item", id=note['id'], title=(note.get('title') or '')[:50]))
            item.setData(Qt.UserRole, note['id'])
            self.note_list.addItem(item)

    def _on_select(self, row):
        if row < 0 or row >= len(self._notes):
            return
        note = self._notes[row]
        self.title_input.setText(note.get('title') or '')
        self.content_input.setPlainText(note.get('content') or '')

    def _save_note(self):
        title = self.title_input.text().strip()
        content = self.content_input.toPlainText().strip()
        if not title:
            return

        current_row = self.note_list.currentRow()
        if current_row >= 0 and current_row < len(self._notes):
            note_id = self._notes[current_row]['id']
            self.memory_manager.update_note(note_id, title=title, content=content)
        else:
            self.memory_manager.add_note(title, content)

        self._load_notes()

    def _delete_note(self):
        current_row = self.note_list.currentRow()
        if current_row >= 0 and current_row < len(self._notes):
            note_id = self._notes[current_row]['id']
            self.memory_manager.delete_note(note_id)
            self._load_notes()
            self.title_input.clear()
            self.content_input.clear()

    def _new_note(self):
        self.note_list.clearSelection()
        self.title_input.clear()
        self.content_input.clear()
        self.title_input.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
