import ctypes
import datetime
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout,
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


class RemindersDialog(QDialog):
    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self.setWindowTitle(self.i18n.t("dialogs.reminders.title"))
        self.setMinimumSize(500, 360)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_reminders()
        _force_taskbar_entry(self)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.i18n.t("dialogs.reminders.active_reminders")))
        self.reminder_list = QListWidget()
        layout.addWidget(self.reminder_list)

        layout.addWidget(QLabel(self.i18n.t("dialogs.reminders.new_reminder")))
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(self.i18n.t("dialogs.reminders.message_placeholder"))
        layout.addWidget(self.message_input)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel(self.i18n.t("dialogs.reminders.minutes_from_now")))
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 1440)
        self.minutes_spin.setValue(30)
        time_layout.addWidget(self.minutes_spin)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton(self.i18n.t("dialogs.reminders.add"))
        self.add_btn.clicked.connect(self._add_reminder)
        btn_layout.addWidget(self.add_btn)

        self.cancel_btn = QPushButton(self.i18n.t("dialogs.reminders.cancel_selected"))
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self._cancel_reminder)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _load_reminders(self):
        self.reminder_list.clear()
        reminders = self.memory_manager.list_reminders(active_only=True)
        self._reminders = reminders
        for r in reminders:
            item = QListWidgetItem(self.i18n.t("commands.reminder_item", id=r['id'], message=(r.get('message') or '')[:50], time=r['trigger_time'][:16]))
            item.setData(Qt.UserRole, r['id'])
            self.reminder_list.addItem(item)

    def _add_reminder(self):
        message = self.message_input.text().strip()
        if not message:
            return
        minutes = self.minutes_spin.value()
        trigger_time = (
            datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        ).strftime("%Y-%m-%d %H:%M:%S")
        self.memory_manager.add_reminder(message, trigger_time)
        self.message_input.clear()
        self._load_reminders()

    def _cancel_reminder(self):
        current = self.reminder_list.currentItem()
        if current:
            reminder_id = current.data(Qt.UserRole)
            self.memory_manager.deactivate_reminder(reminder_id)
            self._load_reminders()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
