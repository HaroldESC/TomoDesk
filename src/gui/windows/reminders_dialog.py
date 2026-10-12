import datetime

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from src.gui.utils import confirm, force_taskbar_entry


def _trigger_time(reminder: dict) -> str:
    """Fecha del recordatorio sin los segundos, tolerante a valores raros.

    SQLite guarda ``"YYYY-MM-DD HH:MM:SS"``; el listado enseña solo minutos.
    Si el valor falta o no es texto se muestra vacío en vez de reventar.
    """
    raw = reminder.get("trigger_time")
    if not isinstance(raw, str):
        return ""
    return raw[:16]


class RemindersDialog(QDialog):
    """Recordatorios activos con alta por teclado y cancelación confirmada."""

    def __init__(self, memory_manager, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.i18n = i18n
        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self._reminders: list = []
        self.setWindowTitle(self.i18n.t("dialogs.reminders.title"))
        self.setMinimumSize(500, 360)
        self.setStyleSheet(styles["dialog"])
        self._setup_ui()
        self._load_reminders()
        force_taskbar_entry(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        reminders_label = QLabel(self.i18n.t("dialogs.reminders.active_reminders"))
        self.reminder_list = QListWidget()
        self.reminder_list.setAccessibleName(
            self.i18n.t("dialogs.reminders.active_reminders")
        )
        # Cancelar solo tiene sentido con un recordatorio seleccionado: el
        # botón se habilita y se deshabilita con la selección.
        self.reminder_list.currentItemChanged.connect(self._update_action_state)
        reminders_label.setBuddy(self.reminder_list)
        layout.addWidget(reminders_label)
        layout.addWidget(self.reminder_list, stretch=1)

        self.empty_label = QLabel(self.i18n.t("dialogs.reminders.empty"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label, stretch=1)

        message_label = QLabel(self.i18n.t("dialogs.reminders.new_reminder"))
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(self.i18n.t("dialogs.reminders.message_placeholder"))
        # Escribir el recordatorio y pulsar Enter lo crea: no hace falta ir
        # hasta el botón con el ratón.
        self.message_input.returnPressed.connect(self._add_reminder)
        message_label.setBuddy(self.message_input)
        layout.addWidget(message_label)
        layout.addWidget(self.message_input)

        time_layout = QHBoxLayout()
        minutes_label = QLabel(self.i18n.t("dialogs.reminders.minutes_from_now"))
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 1440)
        self.minutes_spin.setValue(30)
        minutes_label.setBuddy(self.minutes_spin)
        time_layout.addWidget(minutes_label)
        time_layout.addWidget(self.minutes_spin)
        time_layout.addStretch()
        layout.addLayout(time_layout)

        btn_layout = QHBoxLayout()

        self.add_btn = QPushButton(self.i18n.t("dialogs.reminders.add"))
        self.add_btn.clicked.connect(self._add_reminder)
        btn_layout.addWidget(self.add_btn)

        self.cancel_btn = QPushButton(self.i18n.t("dialogs.reminders.cancel_selected"))
        # Cancelar un recordatorio lo desactiva: es una accion destructiva.
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setToolTip(self.i18n.t("dialogs.reminders.cancel_tip"))
        self.cancel_btn.clicked.connect(self._cancel_reminder)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # Recorrido de Tab natural: listado -> alta -> botones.
        QWidget.setTabOrder(self.reminder_list, self.message_input)
        QWidget.setTabOrder(self.message_input, self.minutes_spin)
        QWidget.setTabOrder(self.minutes_spin, self.add_btn)
        QWidget.setTabOrder(self.add_btn, self.cancel_btn)

    def _load_reminders(self) -> None:
        """Rellena el listado con los recordatorios que siguen activos."""
        reminders = self.memory_manager.list_reminders(active_only=True) or []
        self._reminders = reminders

        blocker = QSignalBlocker(self.reminder_list)
        self.reminder_list.clear()
        for r in reminders:
            item = QListWidgetItem(
                self.i18n.t(
                    "commands.reminder_item",
                    id=r.get('id'),
                    message=(r.get('message') or '')[:50],
                    time=_trigger_time(r),
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, r.get('id'))
            item.setToolTip(r.get('message') or '')
            self.reminder_list.addItem(item)
        del blocker

        empty = self.reminder_list.count() == 0
        self.empty_label.setVisible(empty)
        self.reminder_list.setVisible(not empty)
        self._update_action_state()

    def _update_action_state(self) -> None:
        """Habilita Cancelar solo con un recordatorio seleccionado.

        Mismo patrón que ``settings_dialog``: un botón gris comunica que la
        acción no está disponible en vez de fallar en silencio.
        """
        self.cancel_btn.setEnabled(self.reminder_list.currentItem() is not None)

    def _add_reminder(self) -> None:
        """Crea un recordatorio con el mensaje y los minutos escritos."""
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

    def _cancel_reminder(self) -> None:
        """Desactiva el recordatorio seleccionado previa confirmación."""
        current = self.reminder_list.currentItem()
        if current is None:
            self._update_action_state()
            return
        if not confirm(
            self,
            self.i18n,
            title_key="dialogs.reminders.cancel_confirm_title",
            body_key="dialogs.reminders.cancel_confirm_body",
        ):
            return
        self.memory_manager.deactivate_reminder(
            current.data(Qt.ItemDataRole.UserRole)
        )
        self._load_reminders()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
