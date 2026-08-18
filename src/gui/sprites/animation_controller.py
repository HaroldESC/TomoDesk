"""AnimationController: motor de reproducción de clips del Sprite Pack.

Responsabilidad única: reproducir clips. No decide cuándo ni qué intención usar
(eso es tarea del resolver). Recibe una :class:`SpritePackData` y resuelve la
intención a un clip mediante ``intent_map`` + ``fallbacks``.
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtGui import QPixmap

from src.core.intents import VisualIntent
from src.gui.sprites.sprite_models import AnimationClip, ClipFrame, SpritePackData

logger = logging.getLogger(__name__)


class AnimationController:
    def __init__(self, pack: SpritePackData, frames: Dict[str, List[QPixmap]]):
        self._pack = pack
        self._frames = frames

        self.current_intent: str = VisualIntent.IDLE.value
        self.current_clip_name: str = ""
        self.current_frame_index: int = 0
        self.frame_elapsed_ms: float = 0.0

        self._variant_clip_name: Optional[str] = None
        self._ping_pong_dir: int = 1

        self._transition_frames: Optional[List[QPixmap]] = None
        self._transition_durations: Optional[List[int]] = None
        self._transition_frame_index: int = 0
        self._pending_clip: Optional[str] = None
        self._pending_intent: Optional[str] = None

        self._queued_intent: Optional[str] = None
        self._queued_emotion: Optional[dict] = None
        self._base_speed: float = 1.0

        self._overlay_clip: Optional[AnimationClip] = None
        self._overlay_frame_index: int = 0
        self._overlay_frame_elapsed: float = 0.0
        self._overlay_elapsed_ms: float = 0.0

        self._select_initial()

    # ── Resolución de intents ────────────────────────────────────────────

    def _resolve_clip(self, intent: str) -> str:
        clip = self._pack.intent_map.get(intent)
        if clip and clip in self._pack.clips and clip in self._frames:
            return clip

        seen = set()
        current = intent
        while current not in seen:
            seen.add(current)
            fallback = self._pack.fallbacks.get(current)
            if not fallback or fallback == current:
                break
            current = fallback
            clip = self._pack.intent_map.get(current)
            if clip and clip in self._pack.clips and clip in self._frames:
                return clip

        idle_clip = self._pack.intent_map.get(VisualIntent.IDLE.value)
        if idle_clip and idle_clip in self._pack.clips and idle_clip in self._frames:
            return idle_clip

        for cname in self._pack.clips:
            if cname in self._frames:
                return cname
        return ""

    def request_intent(self, intent,
                       emotion_state: Optional[dict] = None) -> bool:
        if isinstance(intent, VisualIntent):
            intent = intent.value
        clip_name = self._resolve_clip(intent)
        if not clip_name:
            logger.warning(f"Unknown intent '{intent}', ignoring")
            return False

        if clip_name == self.current_clip_name and self._transition_frames is None:
            if self._apply_variant(clip_name, emotion_state):
                self.current_frame_index = 0
                self.frame_elapsed_ms = 0.0
            return True

        current = self._pack.clips.get(self.current_clip_name)
        if current and not current.interruptible and current.mode in ("loop", "hold"):
            self._queued_intent = intent
            self._queued_emotion = emotion_state
            return False

        self._apply_variant(clip_name, emotion_state)

        transition_key = f"{self.current_clip_name}_to_{clip_name}"
        trans_cfg = self._pack.transitions.get(transition_key)
        if trans_cfg:
            t_frames = self._load_transition_frames(trans_cfg)
            if t_frames:
                self._transition_frames = t_frames
                self._transition_durations = trans_cfg.get("frame_durations", [100])
                self._transition_frame_index = 0
                self.frame_elapsed_ms = 0.0
                self._pending_clip = clip_name
                self._pending_intent = intent
                return True

        self._switch_now(clip_name, intent)
        return True

    def force_intent(self, intent,
                     emotion_state: Optional[dict] = None) -> None:
        if isinstance(intent, VisualIntent):
            intent = intent.value
        clip_name = self._resolve_clip(intent)
        if not clip_name:
            return
        self._transition_frames = None
        self._transition_durations = None
        self._transition_frame_index = 0
        self._pending_clip = None
        self._pending_intent = None
        self._queued_intent = None
        self._queued_emotion = None
        self._apply_variant(clip_name, emotion_state)
        self._switch_now(clip_name, intent)

    def _apply_variant(self, clip_name: str,
                       emotion_state: Optional[dict]) -> bool:
        clip = self._pack.clips.get(clip_name)
        new_variant = None
        if clip and clip.variants and emotion_state:
            for vname, vcfg in clip.variants.items():
                condition = vcfg.get("condition", {})
                if self._matches_condition(condition, emotion_state):
                    vclip = vcfg.get("clip")
                    if vclip and vclip in self._pack.clips and vclip in self._frames:
                        new_variant = vclip
                        break
        if new_variant != self._variant_clip_name:
            self._variant_clip_name = new_variant
            return True
        return False

    def _matches_condition(self, condition: dict, emotion_state: dict) -> bool:
        for var, (lo, hi) in condition.items():
            val = emotion_state.get(var, 0.5)
            if not (lo <= val <= hi):
                return False
        return True

    def _switch_now(self, clip_name: str, intent: str):
        self.current_intent = intent
        self.current_clip_name = clip_name
        self.current_frame_index = 0
        self.frame_elapsed_ms = 0.0
        self._ping_pong_dir = 1
        self._queued_intent = None
        self._queued_emotion = None
        self._reset_overlay()

    def _reset_overlay(self):
        self._overlay_clip = None
        self._overlay_frame_index = 0
        self._overlay_frame_elapsed = 0.0
        self._overlay_elapsed_ms = 0.0

    # ── Reproducción ──────────────────────────────────────────────────────

    def update(self, dt_ms: float):
        scaled_dt = dt_ms * self._base_speed
        if self._transition_frames is not None:
            self._advance_transition(scaled_dt)
            return
        self._advance_overlay(dt_ms)
        self._advance_active(scaled_dt)

    def _advance_transition(self, dt_ms: float):
        self.frame_elapsed_ms += dt_ms
        durations = self._transition_durations or [100]
        duration = durations[min(self._transition_frame_index, len(durations) - 1)]
        if self.frame_elapsed_ms < duration:
            return
        self.frame_elapsed_ms = 0.0
        self._transition_frame_index += 1
        if self._transition_frame_index >= len(self._transition_frames or []):
            pending_clip = self._pending_clip
            pending_intent = self._pending_intent
            self._transition_frames = None
            self._transition_durations = None
            self._transition_frame_index = 0
            self._pending_clip = None
            self._pending_intent = None
            if pending_clip:
                self._switch_now(pending_clip, pending_intent or self.current_intent)

    def _advance_overlay(self, dt_ms: float):
        base = self._active_clip()
        overlay_name = None
        if base and base.overlays:
            for name in base.overlays:
                oc = self._pack.clips.get(name)
                if oc and oc.mode == "timed" and name in self._frames:
                    overlay_name = name
                    break

        if self._overlay_clip is None:
            if overlay_name is None:
                return
            self._overlay_elapsed_ms += dt_ms
            oc = self._pack.clips[overlay_name]
            if self._overlay_elapsed_ms >= oc.interval_ms:
                self._overlay_clip = oc
                self._overlay_frame_index = 0
                self._overlay_frame_elapsed = 0.0
                self._overlay_elapsed_ms = 0.0
            return

        oc = self._overlay_clip
        frames = self._frames.get(oc.name, [])
        if not frames:
            self._overlay_clip = None
            return
        durations = [f.duration_ms for f in oc.frames]
        self._overlay_frame_elapsed += dt_ms
        duration = durations[min(self._overlay_frame_index, len(durations) - 1)]
        if self._overlay_frame_elapsed < duration:
            return
        self._overlay_frame_elapsed = 0.0
        self._overlay_frame_index += 1
        if self._overlay_frame_index >= len(frames):
            self._overlay_clip = None
            self._overlay_frame_index = 0

    def _advance_active(self, dt_ms: float):
        clip = self._active_clip()
        frames = self._frames.get(clip.name, [])
        if not frames:
            return
        durations = [f.duration_ms for f in clip.frames]
        self.frame_elapsed_ms += dt_ms
        duration = durations[min(self.current_frame_index, len(durations) - 1)]
        time_scale = max(0.01, self._base_speed)
        if self.frame_elapsed_ms < duration / time_scale:
            return
        self.frame_elapsed_ms = 0.0

        if clip.mode == "ping_pong":
            self.current_frame_index += self._ping_pong_dir
            if self.current_frame_index < 0:
                self.current_frame_index = 1
                self._ping_pong_dir = 1
            elif self.current_frame_index >= len(frames):
                self.current_frame_index = len(frames) - 2
                self._ping_pong_dir = -1
            return

        self.current_frame_index += 1
        if self.current_frame_index >= len(frames):
            if clip.mode == "once":
                if clip.return_to:
                    self.request_intent(clip.return_to)
                    return
                self.current_frame_index = len(frames) - 1
            elif clip.mode == "hold":
                self.current_frame_index = len(frames) - 1
            else:
                self.current_frame_index = 0
        self._check_queued()

    def _check_queued(self):
        if self._queued_intent is not None:
            qs = self._queued_intent
            qe = self._queued_emotion
            self._queued_intent = None
            self._queued_emotion = None
            self.request_intent(qs, qe)

    # ── Salida ────────────────────────────────────────────────────────────

    def get_current_pixmap(self) -> QPixmap:
        if self._transition_frames is not None:
            idx = min(self._transition_frame_index, len(self._transition_frames) - 1)
            return self._transition_frames[idx]

        if self._overlay_clip is not None:
            frames = self._frames.get(self._overlay_clip.name, [])
            if frames:
                idx = min(self._overlay_frame_index, len(frames) - 1)
                return frames[idx]

        clip = self._active_clip()
        frames = self._frames.get(clip.name, [])
        if not frames:
            return self._fallback_pixmap()
        idx = min(self.current_frame_index, len(frames) - 1)
        return frames[idx]

    def _active_clip(self) -> AnimationClip:
        name = self._variant_clip_name or self.current_clip_name
        clip = self._pack.clips.get(name)
        if clip is not None:
            return clip
        return self._fallback_clip()

    def _fallback_clip(self) -> AnimationClip:
        return AnimationClip(
            name="__fallback__",
            mode="hold",
            frames=[ClipFrame(file="__fallback__", duration_ms=1000)],
        )

    def _fallback_pixmap(self) -> QPixmap:
        w = int(self._pack.assets.get("frame_width", 150))
        h = int(self._pack.assets.get("frame_height", 150))
        pix = QPixmap(w, h)
        pix.fill()
        return pix

    def _select_initial(self):
        clip_name = self._resolve_clip(VisualIntent.IDLE.value)
        if clip_name:
            self._switch_now(clip_name, VisualIntent.IDLE.value)

    def _load_transition_frames(self, trans_cfg: dict) -> List[QPixmap]:
        pixmaps: List[QPixmap] = []
        for ref in trans_cfg.get("frames", []):
            pix = self._frames.get(ref)
            if pix:
                pixmaps.extend(pix)
        return pixmaps

    def set_speed(self, multiplier: float):
        self._base_speed = max(0.01, multiplier)