import ctypes
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
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


class MemoriesDialog(QDialog):
    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self.setWindowTitle(self.i18n.t("dialogs.memories.title"))
        self.setMinimumSize(500, 360)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_memories()
        _force_taskbar_entry(self)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.i18n.t("dialogs.memories.saved_memories")))
        self.memory_list = QListWidget()
        layout.addWidget(self.memory_list)

        btn_layout = QHBoxLayout()

        self.delete_btn = QPushButton(self.i18n.t("dialogs.memories.delete"))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete_memory)
        btn_layout.addWidget(self.delete_btn)

        self.refresh_btn = QPushButton(self.i18n.t("dialogs.memories.refresh"))
        self.refresh_btn.clicked.connect(self._load_memories)
        btn_layout.addWidget(self.refresh_btn)

        layout.addLayout(btn_layout)

    def _load_memories(self):
        self.memory_list.clear()
        memories = self.memory_manager.list_episodic_log()
        self._memories = memories
        for m in memories:
            stars = "\u2605" * min(5, int(m["importance_score"] * 5))
            item = QListWidgetItem(
                self.i18n.t("commands.memory_item", id=m['id'], stars=stars, source=m['source'], summary=(m.get('summary') or '')[:70])
            )
            item.setData(Qt.UserRole, m['id'])
            self.memory_list.addItem(item)

    def _delete_memory(self):
        current = self.memory_list.currentItem()
        if current:
            memory_id = current.data(Qt.UserRole)
            self.memory_manager.delete_episodic_memory(memory_id)
            self._load_memories()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
