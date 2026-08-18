import json
import logging
import time
from pathlib import Path

import yaml

from PySide6.QtCore import Qt, QPoint, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QPainter, QPaintEvent, QGuiApplication, QCursor, QWheelEvent
from PySide6.QtWidgets import QWidget, QApplication, QMenu

from src.config.config import get_config_path
from src.core.intents import VisualIntent
from src.gui.styles.styles import get_style_set
from src.gui.sprites.sprite_manager import SpriteManager
from src.gui.widgets.speech_bubble import SpeechBubble
from src.gui.managers.hint_manager import HintManager
from src.gui.managers.window_sitting import WindowSittingController
from src.system.window_manager import WindowManager

logger = logging.getLogger(__name__)


class OverlayWindow(QWidget):
    double_clicked = Signal()
    message_sent = Signal(str)
    restart_requested = Signal()
    _bubble_text_signal = Signal(str, bool)  # thread-safe: text, animate
    _bubble_thinking_signal = Signal()
    _bubble_hide_signal = Signal()
    _assistant_response_signal = Signal(str)  # thread-safe: set last assistant message

    def __init__(self, memory_manager, i18n, config, parent=None, pack_manager=None, state_manager=None, event_monitor=None):
        super().__init__(parent)

        self.memory_manager = memory_manager
        self.i18n = i18n
        self.config = config
        self.state_manager = state_manager
        self._event_monitor = event_monitor
        self._last_interaction_time = time.time()
        self._sleep_timeout = config.get("ui", {}).get("sleep_timeout_seconds", 300)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.NoDropShadowWindowHint
        )

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.NoFocus)

        self.character_size = config.get("ui", {}).get("character_size", 150)
        self.setFixedSize(self.character_size, self.character_size)

        theme = config.get("ui", {}).get("theme", "light")
        self._styles = get_style_set(theme)

        self.dragging = False
        self.drag_position = QPoint()

        self.sprite_manager = SpriteManager(config, "data/sprites")
        self.sprite_manager.frame_timer.setParent(self)
        self._last_sprite_key = (None, None)
        def _on_sprite_tick():
            sm = self.sprite_manager
            key = (sm.current_state, sm.current_frame)
            if key != self._last_sprite_key:
                self._last_sprite_key = key
                self.update()
        self.sprite_manager.frame_timer.timeout.connect(_on_sprite_tick)

        self.wm = WindowManager()
        self.sitting_ctrl = None
        sitting_config = config.get("window_sitting", {})
        if sitting_config.get("enabled", True):
            self.sitting_ctrl = WindowSittingController(
                self, self.sprite_manager, config, self.wm
            )
        self.sitting_timer = QTimer(self)
        self.sitting_timer.timeout.connect(self._update_sitting)
        self.sitting_timer.start(1000)

        bubble_style = config.get("ui", {}).get("bubble_style", "dark")
        max_lines = config.get("ui", {}).get("bubble_max_lines", 5)
        fade_delay = config.get("ui", {}).get("bubble_fade_delay_ms", 4000)
        typewriter_interval = config.get("ui", {}).get("bubble_typewriter_interval_ms", 30)
        self.bubble = SpeechBubble(self, style=bubble_style,
                                   max_lines=max_lines,
                                   fade_delay_ms=fade_delay,
                                   typewriter_interval_ms=typewriter_interval,
                                   i18n=i18n)
        self.bubble.clicked.connect(self._on_bubble_clicked)
        self.bubble.message_sent.connect(self.message_sent)
        self.bubble.double_clicked.connect(self.double_clicked)
        self.bubble.resized.connect(self._update_bubble_position)
        self.bubble.typewriter_finished.connect(lambda: self.set_talking(False))
        self._update_bubble_position()

        self.last_assistant_message = ""
        self._last_bubble_text = ""

        self.hint_manager = HintManager(memory_manager, i18n, config)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._on_first_hover)
        self._hover_occurred = False

        self._double_click_hint_timer = QTimer(self)
        self._double_click_hint_timer.setSingleShot(True)
        self._double_click_hint_timer.timeout.connect(self._show_double_click_hint)

        self._bubble_hint_shown_for_session = False

        self._sleep_check_timer = QTimer(self)
        self._sleep_check_timer.timeout.connect(self._check_sleep)
        self._sleep_check_timer.start(3000)

        self._bubble_text_signal.connect(self.show_bubble_text)
        self._bubble_thinking_signal.connect(self.show_bubble_thinking)
        self._bubble_hide_signal.connect(self.hide_bubble)
        self._assistant_response_signal.connect(self.set_last_assistant_message)

        self._zoom_save_timer = QTimer(self)
        self._zoom_save_timer.setSingleShot(True)
        self._zoom_save_timer.timeout.connect(self._save_zoom_config)

        self.pack_manager = pack_manager
        self.setAcceptDrops(True)
        self._callbacks = {}

        self._load_position()
        self._ensure_visible()

        logger.info("Overlay window initialized")

    def _load_position(self):
        try:
            pos_json = self.memory_manager.get_preference("overlay_position")
            if pos_json:
                pos_data = json.loads(pos_json)
                x = pos_data.get("x")
                y = pos_data.get("y")
                if x is not None and y is not None:
                    self.move(x, y)
                    logger.info(f"Loaded overlay position: ({x}, {y})")
                    return
        except Exception as e:
            logger.warning(f"Failed to load overlay position: {e}")

        screen = QApplication.primaryScreen().geometry()
        default_x = screen.width() - self.width() - 20
        default_y = screen.height() - self.height() - 60
        self.move(default_x, default_y)
        logger.info(f"Using default overlay position: ({default_x}, {default_y})")

    def _save_position(self):
        pos = self.pos()
        try:
            pos_json = json.dumps({"x": pos.x(), "y": pos.y()})
            self.memory_manager.set_preference("overlay_position", pos_json)
            logger.debug(f"Saved overlay position: ({pos.x()}, {pos.y()})")
        except Exception as e:
            logger.warning(f"Failed to save overlay position: {e}")

    def _ensure_visible(self):
        screen = QApplication.primaryScreen().geometry()
        pos = self.pos()
        margin = 50

        new_x = max(screen.left() + margin, min(pos.x(), screen.right() - self.width() - margin))
        new_y = max(screen.top() + margin, min(pos.y(), screen.bottom() - self.height() - margin))

        if new_x != pos.x() or new_y != pos.y():
            self.move(new_x, new_y)
            logger.info(f"Moved overlay to visible area: ({new_x}, {new_y})")

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pixmap = self.sprite_manager.get_current_pixmap()
        if not pixmap.isNull():
            rect = self.rect()
            pix_rect = pixmap.rect()
            x = (rect.width() - pix_rect.width()) // 2
            y = (rect.height() - pix_rect.height()) // 2
            painter.drawPixmap(x, y, pixmap)

    def _update_bubble_position(self):
        bubble = getattr(self, 'bubble', None)
        if not bubble or not bubble.isVisible() or getattr(bubble, '_drag_active', False):
            return
        bubble_width = bubble.width()
        bubble_height = bubble.height()

        char_rect = self.geometry()
        screen = self.screen().availableGeometry()

        ideal_x = char_rect.center().x() - bubble_width // 2
        ideal_y = char_rect.top() - bubble_height - 5

        if ideal_x + bubble_width > screen.right():
            ideal_x = screen.right() - bubble_width
        if ideal_x < screen.left():
            ideal_x = screen.left()

        flipped = ideal_y < screen.top()
        if flipped:
            ideal_y = char_rect.bottom() + 5
            if ideal_y + bubble_height > screen.bottom():
                ideal_y = screen.bottom() - bubble_height
                if ideal_y < screen.top():
                    ideal_y = screen.top()

        bubble.set_flipped(flipped)
        bubble.move(ideal_x, ideal_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bubble_position()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._update_bubble_position()

    def show_bubble_text(self, text: str, animate: bool = True,
                         reset_timer: bool = True):
        self._last_bubble_text = text
        self.set_talking(True)
        self.bubble.show_text(text, animate)
        self._update_bubble_position()
        self._maybe_show_bubble_click_hint()
        if reset_timer:
            self._reset_sleep_timer()
        if not animate:
            QTimer.singleShot(500, lambda: self.set_talking(False))

    def show_bubble_thinking(self):
        self.bubble.show_thinking()
        self._update_bubble_position()
        self._reset_sleep_timer()

    def hide_bubble(self):
        self.bubble.hide_bubble()

    def _update_sitting(self):
        if self.sitting_ctrl is not None:
            self.sitting_ctrl.update()

    def set_animation_state(self, state: str):
        emotion = self.state_manager.get_state() if self.state_manager else None
        self.sprite_manager.set_state(state, emotion)
        self.update()

    def start_animation(self):
        self.sprite_manager.start_animation()

    def stop_animation(self):
        self.sprite_manager.stop_animation()

    def set_talking(self, talking: bool):
        if self.current_state() == VisualIntent.SLEEPING.value:
            return
        if talking:
            self.set_animation_state(VisualIntent.TALKING)
        else:
            self.set_animation_state(VisualIntent.IDLE)

    def enterEvent(self, event):
        self._reset_sleep_timer()
        if not self._hover_occurred:
            self._hover_timer.start(2000)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        super().leaveEvent(event)

    def _on_first_hover(self):
        if not self._hover_occurred:
            self._hover_occurred = True
            cursor_pos = self.mapToGlobal(self.rect().center())
            self.hint_manager.show_drag_hint(cursor_pos, self)
            QTimer.singleShot(5000, lambda: self.hint_manager.show_click_hint(cursor_pos, self))

    def _show_double_click_hint(self):
        self.hint_manager.show_double_click_hint(self.mapToGlobal(self.rect().center()), self)

    def _maybe_show_bubble_click_hint(self):
        if not self._bubble_hint_shown_for_session and self.bubble.isVisible():
            self._bubble_hint_shown_for_session = True
            bubble_center = self.bubble.mapToGlobal(self.bubble.rect().center())
            self.hint_manager.show_bubble_click_hint(bubble_center, self)

    def _on_bubble_clicked(self):
        self._reset_sleep_timer()
        self.bubble.toggle_inline_input()

    def set_last_assistant_message(self, message: str):
        self.last_assistant_message = message

    def _is_click_on_bubble(self, global_pos: QPoint) -> bool:
        if not self.bubble or not self.bubble.isVisible():
            return False
        bubble_global = self.bubble.geometry()
        bubble_global.moveTopLeft(self.bubble.mapToGlobal(QPoint(0, 0)))
        return bubble_global.contains(global_pos)

    def _show_last_message_in_bubble(self):
        if self.last_assistant_message:
            self.show_bubble_text(self.last_assistant_message, animate=False)
        elif self._last_bubble_text:
            self.show_bubble_text(self._last_bubble_text, animate=False)
        else:
            greeting = self.i18n.t("interaction.no_last_message", default="Hello! How can I help?")
            self.show_bubble_text(greeting, animate=False)

    def dragEnterEvent(self, event):
        self._reset_sleep_timer()
        if event.mimeData().hasFormat("text/uri-list") and event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if filepath.lower().endswith(".zip") and self._validate_zip(Path(filepath)):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _validate_zip(self, path: Path) -> bool:
        from src.personality.zip_security import validate_zip_archive
        return validate_zip_archive(path)

    def dropEvent(self, event):
        import shutil
        for url in event.mimeData().urls():
            filepath = Path(url.toLocalFile())
            if filepath.suffix.lower() == ".zip" and self._validate_zip(filepath):
                dest = Path(self.config.get("personality_packs", {}).get("directory", "data/personality_packs")) / filepath.name
                try:
                    shutil.copy2(str(filepath), str(dest))
                except OSError as e:
                    logger.error(f"Failed to copy ZIP: {e}")
                    self.show_bubble_text(
                        self.i18n.t("personality.pack_install_error",
                                    default="Could not install pack.")
                    )
                    event.acceptProposedAction()
                    return
                if self.pack_manager is not None:
                    self.pack_manager.scan_packs()
                self.show_bubble_text(
                    self.i18n.t("personality.pack_installed",
                                default="Personality pack installed!")
                )
                event.acceptProposedAction()
                return
        event.ignore()

    def mousePressEvent(self, event):
        self._reset_sleep_timer()
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._drag_start_global = event.globalPosition().toPoint()
            if self.sitting_ctrl is not None:
                self.sitting_ctrl.pause_on_drag()
            event.accept()
        elif event.button() == Qt.RightButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            self._save_position()
            moved = (event.globalPosition().toPoint() - self._drag_start_global).manhattanLength()
            if moved < 5:
                global_pos = event.globalPosition().toPoint()
                if self._is_click_on_bubble(global_pos):
                    self.bubble.show_inline_input()
                else:
                    self._show_last_message_in_bubble()
                    self._double_click_hint_timer.start(4000)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = max(10, self.character_size // 10)
        new_size = self.character_size + (step if delta > 0 else -step)
        new_size = max(50, min(500, new_size))
        if new_size != self.character_size:
            self.set_character_size(new_size)
            self.config.setdefault("ui", {})["character_size"] = new_size
            self._zoom_save_timer.start(500)
            self._show_size_indicator(new_size)
        event.accept()

    def _show_size_indicator(self, size: int):
        self.bubble.show_text(f"{size}px")
        QTimer.singleShot(1200, self.bubble.hide_bubble)

    def _save_zoom_config(self):
        try:
            from src.config.config import save_config
            save_config(self.config, get_config_path())
            logger.debug("Zoom config saved")
        except Exception as e:
            logger.warning(f"Failed to save zoom config: {e}")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._double_click_hint_timer.stop()
            self.hint_manager.mark_hint_shown(HintManager.HINT_DOUBLE_CLICK)
            self.double_clicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self._reset_sleep_timer()
        self.hint_manager.show_right_click_hint(event.globalPos(), self)
        menu = QMenu(self)
        menu.setStyleSheet(self._styles["overlay_menu"])

        actions = {
            "chat":      menu.addAction(self.i18n.t("menu.chat")),
            "notes":     menu.addAction(self.i18n.t("menu.notes")),
            "reminders": menu.addAction(self.i18n.t("menu.reminders")),
            "memories":  menu.addAction(self.i18n.t("menu.episodic_memories")),
        }
        menu.addSeparator()
        actions["settings"] = menu.addAction(self.i18n.t("menu.settings"))
        menu.addSeparator()
        actions["restart"] = menu.addAction(self.i18n.t("menu.restart"))
        actions["exit"] = menu.addAction(self.i18n.t("menu.exit"))

        if self._callbacks:
            for name, action in actions.items():
                if name in self._callbacks:
                    action.triggered.connect(self._callbacks[name])

        actions["restart"].triggered.connect(self.restart_requested.emit)

        menu.exec(event.globalPos())

    def set_context_menu_callbacks(self, callbacks):
        self._callbacks = callbacks

    def _enter_sleeping(self, reason="idle"):
        if self.current_state() == VisualIntent.SLEEPING.value:
            return
        self.set_animation_state(VisualIntent.SLEEPING)
        if reason == "low_energy":
            msg = self.i18n.t("status.sleeping_low_energy",
                              default="So tired... need to rest... 💤")
        else:
            msg = self.i18n.t("status.sleeping",
                              default="Zzz... falling asleep... 💤")
        self.show_bubble_text(msg, reset_timer=False)

    def _check_sleep(self):
        if self.current_state() == VisualIntent.SLEEPING.value:
            if self.state_manager:
                self.state_manager.update("idle", intensity=0.005)
            if self._event_monitor is not None:
                snapshot = self._event_monitor.get_latest()
                if snapshot is not None:
                    idle_sec = snapshot.get("idle_time_seconds", 0)
                    timeout = self.config.get("ui", {}).get("sleep_timeout_seconds", 300)
                    if idle_sec < timeout:
                        self._reset_sleep_timer()
            return
        if self.state_manager and self.config.get("ui", {}).get("sleep_low_energy_enabled", True):
            if time.time() - self._last_interaction_time > 15:
                state = self.state_manager.get_state()
                energy = state.get("energy", 0.5)
                if energy < 0.05:
                    self._enter_sleeping(reason="low_energy")
                    return
        if self._event_monitor is None:
            return
        snapshot = self._event_monitor.get_latest()
        if snapshot is None:
            return
        idle_sec = snapshot.get("idle_time_seconds", 0)
        timeout = self.config.get("ui", {}).get("sleep_timeout_seconds", 300)
        if idle_sec >= timeout:
            self._enter_sleeping(reason="idle")

    def _reset_sleep_timer(self):
        self._last_interaction_time = time.time()
        was_sleeping = self.current_state() == VisualIntent.SLEEPING.value
        if was_sleeping:
            self.set_animation_state(VisualIntent.IDLE)
            self.update()
            if self.state_manager:
                state = self.state_manager.get_state()
                energy = state.get("energy", 0.5)
                if energy < 0.3:
                    wake_msg = self.i18n.t("status.waking_up",
                                           default="Good morning! 😊")
                else:
                    wake_msg = self.i18n.t("status.waking_up_energized",
                                           default="Ahh... I feel much better after that nap! 😊")
                self.show_bubble_text(wake_msg, reset_timer=False)
    def current_state(self):
        return self.sprite_manager.current_state

    def apply_theme(self, theme_name: str):
        styles = get_style_set(theme_name)
        self._styles = styles

    def reload_sprite(self, sprite_name: str = None):
        self.sprite_manager._load_sprite()
        self.update()

    def set_character_size(self, size: int) -> None:
        self.character_size = size
        self.setFixedSize(size, size)
        self.sprite_manager.set_character_size(size)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        logger.info("Overlay window shown")

    def closeEvent(self, event):
        self._save_position()
        super().closeEvent(event)
