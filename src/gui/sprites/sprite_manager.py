import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen

from src.core.intents import VisualIntent, normalize_intent
from src.core.visual_state_resolver import VisualStateResolver
from src.gui.sprites.animation_controller import AnimationController
from src.gui.sprites.sprite_loader import SpriteLoader, SpriteLoadError
from src.gui.sprites.sprite_models import AnimationClip, ClipFrame, SpritePackData

logger = logging.getLogger(__name__)


class SpriteManager:
    def __init__(self, config: dict, sprite_dir: str = "data/sprites",
                 resolver: Optional[VisualStateResolver] = None):
        self.config = config
        self.sprite_dir = Path(sprite_dir)
        self.character_size = config.get("ui", {}).get("character_size", 150)
        self.resolver = resolver
        self._last_emotion: Optional[dict] = None
        self._transient_played = False

        self.animation_controller: Optional[AnimationController] = None
        self._in_error = False
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self._on_timer_tick)
        self._last_tick_time: Optional[float] = None

        self._loader = SpriteLoader(config, sprite_dir)

        self._load_sprite()

        logger.info("SpriteManager initialized")

    def _load_sprite(self):
        ui_config = self.config.get("ui", {})
        sprite_cfg = ui_config.get("sprite", {})

        use_custom = sprite_cfg.get("use_custom", False)
        custom_path = sprite_cfg.get("custom_path", "")
        active = sprite_cfg.get("active", "default")

        if use_custom and custom_path:
            sprite_name = Path(custom_path).name
            sprite_dir = Path(custom_path)
        else:
            sprite_name = active
            sprite_dir = None

        try:
            pack, frames_cache = self._loader.load_sprite(sprite_name, sprite_dir)
            self._in_error = False
        except SpriteLoadError as e:
            logger.error(f"Failed to load sprite '{sprite_name}': {e}")
            error_pix = self._create_error_pixmap(sprite_name)
            pack = SpritePackData(
                id=sprite_name,
                name=sprite_name,
                version="1.0.0",
                assets={
                    "image_format": "png",
                    "frame_width": self.character_size,
                    "frame_height": self.character_size,
                },
                intent_map={VisualIntent.IDLE.value: "error"},
                fallbacks={},
                clips={
                    "error": AnimationClip(
                        name="error",
                        mode="hold",
                        frames=[ClipFrame(file="error", duration_ms=1000)],
                        interruptible=False,
                    )
                },
            )
            frames_cache = {"error": [error_pix]}
            self._in_error = True

        self._scale_frames(frames_cache)

        self.animation_controller = AnimationController(pack, frames_cache)
        self.animation_controller.force_intent(VisualIntent.IDLE)

    def _create_error_pixmap(self, sprite_name: str) -> QPixmap:
        pix = QPixmap(self.character_size, self.character_size)
        pix.fill(QColor(40, 40, 50, 220))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(QPen(QColor(255, 100, 100)))
        p.setFont(QFont("Arial", int(self.character_size * 0.08), QFont.Bold))
        p.drawText(pix.rect(), Qt.AlignCenter,
                   f"Could not load\n\"{sprite_name}\"")

        p.setPen(QPen(QColor(180, 180, 180)))
        p.setFont(QFont("Arial", int(self.character_size * 0.04)))
        r = pix.rect().adjusted(0, int(self.character_size * 0.15), 0, 0)
        p.drawText(r, Qt.AlignCenter, "Check data/sprites/")
        p.end()
        return pix

    def _scale_frames(self, cache: Dict[str, List[QPixmap]]):
        for key, frames in cache.items():
            scaled = []
            for pix in frames:
                if (pix.width() != self.character_size
                        or pix.height() != self.character_size):
                    pix = pix.scaled(self.character_size, self.character_size,
                                     Qt.KeepAspectRatio, Qt.SmoothTransformation)
                scaled.append(pix)
            cache[key] = scaled

    def _on_timer_tick(self):
        import time
        now = time.monotonic()
        if self._last_tick_time is not None:
            dt_ms = (now - self._last_tick_time) * 1000.0
            if self.animation_controller:
                if self.resolver is not None:
                    self._sync_from_resolver()
                self.animation_controller.update(dt_ms)
        self._last_tick_time = now

    def _sync_from_resolver(self):
        if self.resolver is None or self.animation_controller is None:
            return
        if self.resolver.has_transient() and self._transient_played:
            if (self.animation_controller.current_intent
                    != self.resolver.transient_intent()):
                self.resolver.clear_transient()
                self._transient_played = False
        intent = self.resolver.resolve(self._last_emotion)
        accepted = self.animation_controller.request_intent(intent, self._last_emotion)
        if (self.resolver.has_transient()
                and intent == self.resolver.transient_intent() and accepted):
            self._transient_played = True

    def push_event(self, event: str, payload: Optional[dict] = None):
        if self.resolver is not None:
            self.resolver.push_event(event, payload)

    def set_state(self, state, emotion_state: Optional[dict] = None):
        if self._in_error:
            return
        self._last_emotion = emotion_state
        if self.resolver is not None:
            intent = state.value if isinstance(state, VisualIntent) else state
            normalized = normalize_intent(intent)
            if normalized is None:
                return
            agent = normalized if normalized != VisualIntent.IDLE else None
            self.resolver.set_agent_intent(agent)
            logger.debug(f"Agent intent set: {normalized}")
            return
        if self.animation_controller:
            intent = state.value if isinstance(state, VisualIntent) else state
            self.animation_controller.request_intent(intent, emotion_state)
            logger.debug(f"Animation intent requested: {intent}")

    def set_frame_speed(self, multiplier: float):
        if self.animation_controller:
            self.animation_controller.set_speed(multiplier)

    def get_current_pixmap(self) -> QPixmap:
        if not self.animation_controller:
            return QPixmap(self.character_size, self.character_size)
        pix = self.animation_controller.get_current_pixmap()
        show_labels = self.config.get("ui", {}).get("sprite", {}).get("show_frame_labels", False)
        if show_labels:
            pix = QPixmap(pix)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(255, 255, 0)))
            p.setFont(QFont("Consolas", 9, QFont.Bold))
            label = f"{self.current_state} [{self.current_frame}]"
            p.drawText(2, 12, label)
            p.end()
        return pix

    @property
    def current_state(self) -> str:
        if self._in_error:
            return "error"
        if self.animation_controller:
            return self.animation_controller.current_intent
        return VisualIntent.IDLE.value

    @current_state.setter
    def current_state(self, value: str):
        pass

    @property
    def current_frame(self) -> int:
        if self.animation_controller:
            return self.animation_controller.current_frame_index
        return 0

    @current_frame.setter
    def current_frame(self, value: int):
        pass

    def set_character_size(self, size: int) -> None:
        self.character_size = size
        old_state = self.current_state
        self._load_sprite()
        if self.animation_controller:
            if old_state == "error":
                self.animation_controller.force_intent(VisualIntent.IDLE)
            else:
                self.animation_controller.force_intent(old_state)

    def start_animation(self):
        self._last_tick_time = None
        self.frame_timer.start(16)

    def stop_animation(self):
        self.frame_timer.stop()
        self._last_tick_time = None

    @property
    def frames(self) -> Dict[str, List[QPixmap]]:
        if self.animation_controller:
            return getattr(self.animation_controller, "_frames", {})
        return {}

    def is_animating(self) -> bool:
        return self.frame_timer.isActive()