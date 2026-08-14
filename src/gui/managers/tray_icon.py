import logging
import os
import tempfile

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, main_window, config, overlay=None, i18n=None, menu_style=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.config      = config
        self.overlay     = overlay
        self.i18n        = i18n
        self._menu_style = menu_style

        available = QSystemTrayIcon.isSystemTrayAvailable()
        logger.info(f"System tray available: {available}")
        if not available:
            logger.warning("System tray not supported on this platform")

        self._setup_icon()
        self._setup_menu()
        self.activated.connect(self._on_activated)
        self.show()
        self._show_welcome()
        QTimer.singleShot(2000, self._ensure_visible)
        logger.info("Tray icon initialized")

    # ── Icon ──────────────────────────────────────────────────────────────────

    def _make_icon_pixmap(self, size: int) -> QPixmap:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = max(1, size // 16)
        r = size - margin * 2
        painter.setBrush(QColor("#7B85D6"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(margin, margin, r, r, r // 4, r // 4)
        painter.setPen(QColor("#FFFFFF"))
        fs = size * 9 // 16
        painter.setFont(QFont("Segoe UI", fs, QFont.Bold))
        painter.drawText(pix.rect(), Qt.AlignCenter, "T")
        painter.end()
        return pix

    def _setup_icon(self):
        tmp = tempfile.gettempdir()
        ico_path = os.path.join(tmp, "tomodesk_tray.png")
        pix = self._make_icon_pixmap(32)
        pix.save(ico_path)

        icon = QIcon()
        icon.addPixmap(self._make_icon_pixmap(16))
        icon.addPixmap(self._make_icon_pixmap(32))
        self.setIcon(icon)
        name = self.config.get("personality", {}).get("name", "Tomo")
        self.setToolTip(f"TomoDesk — {name}")

    def _ensure_visible(self):
        if not self.isVisible():
            logger.warning("Tray icon not visible, retrying...")
            self.show()
            if not self.isVisible():
                self.setVisible(True)

    def _show_welcome(self):
        t = self.i18n.t if self.i18n else (lambda key, **kw: key)
        self.showMessage(
            t("tray.welcome_title", default="TomoDesk"),
            t("tray.welcome_message", default="Running in the background"),
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _setup_menu(self):
        # Graceful fallback if i18n is not available
        t = self.i18n.t if self.i18n else (lambda key, **kw: key)

        menu = QMenu()
        if self._menu_style:
            menu.setStyleSheet(self._menu_style)

        show_action = QAction(t("menu.show_chat"), self)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)

        menu.addSeparator()

        notes_action = QAction(t("menu.notes"), self)
        notes_action.triggered.connect(self.main_window.open_notes)
        menu.addAction(notes_action)

        reminders_action = QAction(t("menu.reminders"), self)
        reminders_action.triggered.connect(self.main_window.open_reminders)
        menu.addAction(reminders_action)

        menu.addSeparator()

        self.focus_action = QAction(t("menu.focus_mode"), self)
        self.focus_action.setCheckable(True)
        self.focus_action.triggered.connect(self._toggle_focus)
        menu.addAction(self.focus_action)

        menu.addSeparator()

        exit_action = QAction(t("menu.exit"), self)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)

        self.setContextMenu(menu)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main_window()

    def _show_main_window(self):
        from PySide6.QtCore import Qt, QTimer
        self.main_window.setWindowState(
            self.main_window.windowState() & ~Qt.WindowMinimized
        )
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        QTimer.singleShot(100, self.main_window.raise_)
        QTimer.singleShot(100, self.main_window.activateWindow)

    def _toggle_focus(self, checked: bool):
        engine = getattr(self.main_window, "proactive_engine", None)
        if engine:
            engine.policy.set_focus_mode(checked)
        if hasattr(self.main_window, "_update_status_message"):
            self.main_window._update_status_message()

    def set_menu_style(self, style: str):
        self._menu_style = style
        menu = self.contextMenu()
        if menu:
            menu.setStyleSheet(style)

    def _exit_app(self):
        logger.info("Exit via tray icon")
        if self.overlay:
            self.overlay.close()
        self.main_window.quit_application()
        QCoreApplication.quit()
