import datetime
import logging
import os
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMenuBar, QMessageBox, QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from src.system.commands import handle_command, format_proactive_status
from src.gui.widgets.chat_widget import ChatWidget
from src.gui.windows.memories_dialog import MemoriesDialog
from src.gui.windows.notes_dialog import NotesDialog
from src.gui.windows.reminders_dialog import RemindersDialog
from src.gui.windows.settings_dialog import SettingsDialog
from src.gui.styles.styles import get_style_set

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    _assistant_message_signal = Signal(str)
    _system_message_signal = Signal(str)

    def __init__(
        self,
        config,
        memory_manager,
        event_monitor=None,
        context_builder=None,
        proactive_engine=None,
        state_manager=None,
        engine=None,
        reminder_checker=None,
        i18n=None,
        overlay=None,
    ):
        super().__init__()
        self.config = config
        self.memory_manager = memory_manager
        self.event_monitor = event_monitor
        self.context_builder = context_builder
        self.proactive_engine = proactive_engine
        self.state_manager = state_manager
        self.engine = engine
        self.reminder_checker = reminder_checker
        self.i18n = i18n
        self.overlay = overlay

        name = config['personality']['name']
        self.setWindowTitle(self.i18n.t("app.title", name=name))
        self.setMinimumSize(900, 550)
        self.resize(1000, 700)

        theme = config.get("ui", {}).get("theme", "light")
        self._styles = get_style_set(theme)
        self.setStyleSheet(self._styles["main"])
        self._setup_menu()
        self._setup_central()
        self._setup_status_bar()
        self._start_timers()

        self._quit_on_close = False
        self._chat_poller = None

        self._assistant_message_signal.connect(self.add_assistant_message)
        self._system_message_signal.connect(self.add_system_message)

        self.add_system_message(self.i18n.t("status.ready_message", name=name))

    def _setup_menu(self):
        menubar = self.menuBar()
        name = self.config["personality"]["name"]

        # ── Menu: Character name ──
        self._char_menu = menubar.addMenu(name)

        self.toggle_overlay_action = QAction(self.i18n.t("menu.char.show_overlay"), self)
        self.toggle_overlay_action.triggered.connect(self._toggle_overlay)
        self._char_menu.addAction(self.toggle_overlay_action)

        self.focus_mode_action = QAction(self.i18n.t("menu.char.focus_mode"), self)
        self.focus_mode_action.setCheckable(True)
        self.focus_mode_action.setShortcut("Ctrl+F")
        self.focus_mode_action.triggered.connect(self._toggle_focus)
        self._char_menu.addAction(self.focus_mode_action)

        self._clear_chat_action = QAction(self.i18n.t("menu.char.clear_chat"), self)
        self._clear_chat_action.triggered.connect(self._clear_chat)
        self._char_menu.addAction(self._clear_chat_action)

        self._char_menu.addSeparator()
        self._exit_action = QAction(self.i18n.t("menu.char.exit"), self)
        self._exit_action.setShortcut("Ctrl+Q")
        self._exit_action.triggered.connect(self.quit_application)
        self._char_menu.addAction(self._exit_action)

        # ── Menu: Conversation ──
        self._conv_menu = menubar.addMenu(self.i18n.t("menu.conversation.title"))

        self._notes_action = QAction(self.i18n.t("menu.conversation.notes"), self)
        self._notes_action.setShortcut("Ctrl+N")
        self._notes_action.triggered.connect(self.open_notes)
        self._conv_menu.addAction(self._notes_action)

        self._reminders_action = QAction(self.i18n.t("menu.conversation.reminders"), self)
        self._reminders_action.setShortcut("Ctrl+R")
        self._reminders_action.triggered.connect(self.open_reminders)
        self._conv_menu.addAction(self._reminders_action)

        self._episodic_action = QAction(self.i18n.t("menu.conversation.episodic"), self)
        self._episodic_action.setShortcut("Ctrl+E")
        self._episodic_action.triggered.connect(self._open_memories)
        self._conv_menu.addAction(self._episodic_action)

        # ── Settings (top-level action) ──
        self._settings_action = QAction(self.i18n.t("menu.settings"), self)
        self._settings_action.setShortcut("Ctrl+,")
        self._settings_action.triggered.connect(self._open_settings)
        menubar.addAction(self._settings_action)

        # ── Menu: Help ──
        self._help_menu = menubar.addMenu(self.i18n.t("menu.help.title"))

        self._guide_action = QAction(self.i18n.t("menu.help.guide"), self)
        self._guide_action.triggered.connect(self._show_interaction_guide)
        self._help_menu.addAction(self._guide_action)

        self._about_action = QAction(self.i18n.t("menu.help.about"), self)
        self._about_action.triggered.connect(self._show_about)
        self._help_menu.addAction(self._about_action)

    def _setup_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        theme = self.config.get("ui", {}).get("theme", "light")
        self.chat = ChatWidget(i18n=self.i18n, theme=theme)
        layout.addWidget(self.chat, stretch=1)

        input_layout = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(self.i18n.t("chat.input_placeholder"))
        self.input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input, stretch=1)

        self.send_btn = QPushButton(self.i18n.t("chat.send_button"))
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

    def _setup_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.mood_label = QLabel("")
        self.mood_label.setStyleSheet("padding-right: 8px;")
        self.status.addWidget(self.mood_label, stretch=1)

        self._mode_label = QLabel("")
        self._mode_label.setStyleSheet("padding-left: 4px;")
        self.status.addPermanentWidget(self._mode_label)

        self._update_status_message()

    def _update_status_message(self):
        if not self.state_manager:
            return
        state = self.state_manager.get_state()
        idle_sec = 0
        if self.event_monitor:
            try:
                snap = self.event_monitor.get_latest()
                if snap:
                    idle_sec = snap.get("idle_time_seconds", 0)
            except Exception:
                pass

        if idle_sec > 600:
            msg = self.i18n.t("status.sleeping")
        elif state["connection"] < 0.2:
            msg = self.i18n.t("status.distant")
        elif state["energy"] < 0.3:
            msg = self.i18n.t("status.tired")
        elif state["happiness"] > 0.8:
            msg = self.i18n.t("status.radiant")
        elif state["curiosity"] > 0.7:
            msg = self.i18n.t("status.curious")
        else:
            msg = self.i18n.t("status.listening")

        self.mood_label.setText(msg)
        tooltip = (
            f"Happiness: {state['happiness']:.2f}\n"
            f"Energy: {state['energy']:.2f}\n"
            f"Curiosity: {state['curiosity']:.2f}\n"
            f"Closeness: {state['closeness']:.2f}\n"
            f"Connection: {state['connection']:.2f}"
        )
        self.mood_label.setToolTip(tooltip)

        if self.proactive_engine:
            try:
                enabled = self.proactive_engine.policy.is_enabled()
                focus = self.proactive_engine.policy.focus_mode
                if focus:
                    self._mode_label.setText(self.i18n.t("status.focus_mode_indicator"))
                elif not enabled:
                    self._mode_label.setText(self.i18n.t("status.dnd_mode_indicator"))
                else:
                    self._mode_label.setText("")
            except Exception:
                pass

    def _start_timers(self):
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status_message)
        self.status_timer.start(5000)

    def add_system_message(self, text: str):
        self.chat.add_message("system", text)

    def add_user_message(self, text: str):
        self.chat.add_message("user", text)

    def add_assistant_message(self, text: str):
        self.chat.add_message("assistant", text)

    def _send_message(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.add_user_message(text)

        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._handle_chat(text)

    def _handle_command(self, cmd: str):
        try:
            msg, continue_loop = handle_command(
                cmd,
                self.memory_manager,
                self.config,
                self.event_monitor,
                self.context_builder,
                self.proactive_engine,
                self.state_manager,
                i18n=self.i18n,
            )
            if msg:
                self.add_assistant_message(msg)
            if not continue_loop:
                self.close()
        except Exception as e:
            logger.error(f"Command error: {e}", exc_info=True)
            self.add_system_message(self.i18n.t("chat.error_prefix", error=str(e)))

    def process_command(self, cmd: str):
        try:
            msg, continue_loop = handle_command(
                cmd, self.memory_manager, self.config,
                self.event_monitor, self.context_builder,
                self.proactive_engine, self.state_manager,
                i18n=self.i18n,
            )
            if msg:
                self.add_assistant_message(msg)
            if not continue_loop:
                self.close()
            return msg
        except Exception as e:
            logger.error(f"Command error: {e}", exc_info=True)
            self.add_system_message(self.i18n.t("chat.error_prefix", error=str(e)))
            return None

    def _handle_chat(self, text: str):
        if self.overlay:
            self.overlay.show_bubble_thinking()

        def do_chat():
            try:
                response = self.engine.chat(text)
                self._assistant_message_signal.emit(response)
                if self.overlay:
                    self.overlay._bubble_text_signal.emit(response, True)
                    self.overlay._assistant_response_signal.emit(response)
            except Exception as e:
                logger.error(f"Chat error: {e}", exc_info=True)
                self._system_message_signal.emit(self.i18n.t("chat.error_prefix", error=str(e)))
                if self.overlay:
                    self.overlay._bubble_text_signal.emit(f"Error: {e}", False)

        self.send_btn.setEnabled(False)
        self.send_btn.setText(self.i18n.t("chat.thinking"))
        self.input.setEnabled(False)

        if self._chat_poller:
            self._chat_poller.stop()
        self._chat_poller = QTimer(self)
        self._chat_poller.setSingleShot(False)
        t = threading.Thread(target=do_chat, daemon=True)
        t.start()

        def poll():
            if not t.is_alive():
                self._chat_poller.stop()
                self._chat_poller = None
                self.send_btn.setText(self.i18n.t("chat.send_button"))
                self.send_btn.setEnabled(True)
                self.input.setEnabled(True)
                self.input.setFocus()

        self._chat_poller.timeout.connect(poll)
        self._chat_poller.start(100)

    def open_notes(self):
        dialog = NotesDialog(self.memory_manager, self, self.i18n, styles=self._styles)
        dialog.exec()

    def open_reminders(self):
        dialog = RemindersDialog(self.memory_manager, self, self.i18n, styles=self._styles)
        dialog.exec()

    def _open_memories(self):
        dialog = MemoriesDialog(self.memory_manager, self, self.i18n, styles=self._styles)
        dialog.exec()

    def _open_settings(self):
        if hasattr(self, '_settings_dialog') and self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self.config, self.proactive_engine, self, self.i18n,
                                styles=self._styles,
                                context_manager=self.overlay.context_manager if self.overlay else None)
        dialog.sprite_changed.connect(self.reload_sprite)
        dialog.language_changed.connect(self._apply_language)
        dialog.finished.connect(lambda: self._on_settings_closed(dialog))
        self._settings_dialog = dialog
        dialog.show()

    def _on_settings_closed(self, dialog):
        if self.proactive_engine:
            modes = self.config.get("modes", {})
            self.proactive_engine.policy.set_dnd_mode(
                not modes.get("proactive_comments", False)
            )
        if hasattr(self, '_settings_dialog') and self._settings_dialog is dialog:
            self._settings_dialog = None

    def _show_about(self):
        QMessageBox.about(
            self,
            self.i18n.t("app.about_title"),
            f"<h3>TomoDesk v0.1.0</h3>"
            f"<p>{self.i18n.t('app.about_text', name=self.config['personality']['name'], model=self.config['llm']['model'])}</p>"
            f"<hr><p><small>Powered by PySide6 and Ollama</small></p>",
        )

    def _toggle_overlay(self):
        if not self.overlay:
            return
        visible = not self.overlay.isVisible()
        self.overlay.setVisible(visible)
        self.toggle_overlay_action.setText(
            self.i18n.t("menu.char.show_overlay")
        )
        self._update_status_message()

    def _toggle_focus(self, checked: bool):
        if self.proactive_engine:
            self.proactive_engine.policy.set_focus_mode(checked)
        self._update_status_message()

    def _show_interaction_guide(self):
        msg = (
            f"<b>{self.i18n.t('hints.drag')}</b><br><br>"
            f"<b>{self.i18n.t('hints.click')}</b><br><br>"
            f"<b>{self.i18n.t('hints.double_click')}</b><br><br>"
            f"<b>{self.i18n.t('hints.right_click')}</b><br><br>"
            f"<b>{self.i18n.t('hints.bubble_click')}</b>"
        )
        QMessageBox.information(
            self,
            self.i18n.t("menu.help.guide"),
            msg,
        )

    def _clear_chat(self):
        self.chat.clear()
        self.memory_manager.clear_short_term()
        self.add_system_message(self.i18n.t("chat.clear_system_msg"))

    def _apply_language(self):
        name = self.config["personality"]["name"]
        self.setWindowTitle(self.i18n.t("app.title", name=name))
        self.input.setPlaceholderText(self.i18n.t("chat.input_placeholder"))
        self.send_btn.setText(self.i18n.t("chat.send_button"))
        self.toggle_overlay_action.setText(self.i18n.t("menu.char.show_overlay"))
        self.focus_mode_action.setText(self.i18n.t("menu.char.focus_mode"))
        self._clear_chat_action.setText(self.i18n.t("menu.char.clear_chat"))
        self._exit_action.setText(self.i18n.t("menu.char.exit"))
        self._char_menu.setTitle(name)
        self._conv_menu.setTitle(self.i18n.t("menu.conversation.title"))
        self._notes_action.setText(self.i18n.t("menu.conversation.notes"))
        self._reminders_action.setText(self.i18n.t("menu.conversation.reminders"))
        self._episodic_action.setText(self.i18n.t("menu.conversation.episodic"))
        self._settings_action.setText(self.i18n.t("menu.settings"))
        self._help_menu.setTitle(self.i18n.t("menu.help.title"))
        self._guide_action.setText(self.i18n.t("menu.help.guide"))
        self._about_action.setText(self.i18n.t("menu.help.about"))
        self._update_status_message()

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        )

    def closeEvent(self, event):
        if self._quit_on_close:
            logger.info("Main window closing permanently")
            event.accept()
        else:
            logger.info("Hiding to system tray")
            self.hide()
            event.ignore()

    def reload_sprite(self, sprite_name: str = None):
        if self.overlay:
            self.overlay.reload_sprite(sprite_name)

    def apply_theme(self, theme_name: str, character_size: int | None = None):
        styles = get_style_set(theme_name)
        self._styles = styles
        self.setStyleSheet(styles["main"])
        if hasattr(self, "chat") and hasattr(self.chat, "set_theme"):
            self.chat.set_theme(theme_name)
        if character_size is None:
            character_size = self.config.get("ui", {}).get("character_size", 150)
        if self.overlay:
            self.overlay.apply_theme(theme_name)
            self.overlay.set_character_size(character_size)
        if hasattr(self, '_tray_icon'):
            self._tray_icon.set_menu_style(styles["overlay_menu"])

    def quit_application(self):
        self._quit_on_close = True
        QApplication.quit()
