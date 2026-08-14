import json
import logging
from typing import Dict, Optional

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QToolTip

from src.memory.memory import MemoryManager

logger = logging.getLogger(__name__)


class HintManager:
    HINT_DRAG = "drag"
    HINT_CLICK = "click"
    HINT_DOUBLE_CLICK = "double_click"
    HINT_BUBBLE_CLICK = "bubble_click"
    HINT_RIGHT_CLICK = "right_click"

    def __init__(self, memory_manager: MemoryManager, i18n, config: dict):
        self.memory_manager = memory_manager
        self.i18n = i18n
        self.enabled = config.get("ui", {}).get("hints", {}).get("enabled", True)
        self.delay_ms = config.get("ui", {}).get("hints", {}).get("delay_ms", 2000)

        self._shown_hints = set()
        self._load_shown_hints()

    def _load_shown_hints(self):
        if not self.enabled:
            return
        try:
            data = self.memory_manager.get_preference("shown_hints")
            if data:
                self._shown_hints = set(json.loads(data))
        except Exception as e:
            logger.warning(f"Failed to load shown hints: {e}")

    def _save_shown_hints(self):
        if not self.enabled:
            return
        try:
            data = json.dumps(list(self._shown_hints))
            self.memory_manager.set_preference("shown_hints", data)
        except Exception as e:
            logger.warning(f"Failed to save shown hints: {e}")

    def is_hint_shown(self, hint_id: str) -> bool:
        return hint_id in self._shown_hints

    def mark_hint_shown(self, hint_id: str):
        if hint_id not in self._shown_hints:
            self._shown_hints.add(hint_id)
            self._save_shown_hints()

    def show_tooltip(self, text: str, pos: QPoint, parent_widget, delay_ms: Optional[int] = None):
        if not self.enabled:
            return
        delay = delay_ms if delay_ms is not None else self.delay_ms
        QToolTip.showText(pos, text, parent_widget, msecShowTime=delay)

    def show_drag_hint(self, global_pos, parent):
        if not self.enabled or self.is_hint_shown(self.HINT_DRAG):
            return
        self.show_tooltip(self.i18n.t("hints.drag"), global_pos, parent, 3000)
        self.mark_hint_shown(self.HINT_DRAG)

    def show_click_hint(self, global_pos, parent):
        if not self.enabled or self.is_hint_shown(self.HINT_CLICK):
            return
        self.show_tooltip(self.i18n.t("hints.click"), global_pos, parent, 3000)
        self.mark_hint_shown(self.HINT_CLICK)

    def show_double_click_hint(self, global_pos, parent):
        if not self.enabled or self.is_hint_shown(self.HINT_DOUBLE_CLICK):
            return
        self.show_tooltip(self.i18n.t("hints.double_click"), global_pos, parent, 3000)
        self.mark_hint_shown(self.HINT_DOUBLE_CLICK)

    def show_bubble_click_hint(self, bubble_global_pos, parent):
        if not self.enabled or self.is_hint_shown(self.HINT_BUBBLE_CLICK):
            return
        self.show_tooltip(self.i18n.t("hints.bubble_click"), bubble_global_pos, parent, 3000)
        self.mark_hint_shown(self.HINT_BUBBLE_CLICK)

    def show_right_click_hint(self, global_pos, parent):
        if not self.enabled or self.is_hint_shown(self.HINT_RIGHT_CLICK):
            return
        self.show_tooltip(self.i18n.t("hints.right_click"), global_pos, parent, 3000)
        self.mark_hint_shown(self.HINT_RIGHT_CLICK)
