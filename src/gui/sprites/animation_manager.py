import logging
import random
import time
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap

from src.gui.sprites.animation_state import AnimationState
from src.gui.sprites.sprite_models import AnimState, SubAnimation

logger = logging.getLogger(__name__)


class AnimationManager:
    def __init__(self, sprite_config: dict,
                 frames_cache: Dict[str, List[QPixmap]]):
        self._config = sprite_config
        self._frames_cache = frames_cache

        self._states: Dict[str, AnimState] = {}
        self._transitions: Dict[str, dict] = sprite_config.get("transitions", {})

        self._build_states()

        self.current_state_name: str = AnimationState.IDLE
        self.current_frame_index: int = 0
        self.frame_elapsed_ms: float = 0.0

        self._transition_frames: Optional[List[QPixmap]] = None
        self._transition_durations: Optional[List[int]] = None
        self._transition_frame_index: int = 0
        self._pending_state: Optional[str] = None
        self._one_shot_return: Optional[str] = None
        self._queued_state: Optional[str] = None
        self._queued_emotion: Optional[dict] = None
        self._base_speed: float = 1.0

        self._composite_last_pick: float = time.monotonic()

    def _build_states(self):
        states_config = self._config.get("states", {})
        for name, cfg in states_config.items():
            anim_type = cfg.get("type", "simple")
            frames = self._frames_cache.get(name, [])

            if not frames and anim_type in ("simple", "one_shot"):
                logger.warning(f"No frames for state '{name}', using placeholder")
                pix = QPixmap(self._config.get("frame_width", 150),
                              self._config.get("frame_height", 150))
                pix.fill()
                frames = [pix]

            if anim_type == "composite":
                sub_animations = []
                for sub_cfg in cfg.get("animations", []):
                    sub_frames = self._frames_cache.get(f"{name}/{sub_cfg['name']}", frames)
                    if not sub_frames:
                        continue
                    sub_animations.append(SubAnimation(
                        name=sub_cfg["name"],
                        frames=sub_frames,
                        durations=sub_cfg.get("frame_durations", [100]),
                        loop=sub_cfg.get("loop", True),
                        weight=sub_cfg.get("weight", 1),
                        cooldown_ms=sub_cfg.get("cooldown_ms", 0),
                    ))
                state = AnimState(
                    name=name, anim_type="composite",
                    frames=[], durations=[],
                    loop=True, interruptible=True,
                    sub_animations=sub_animations,
                    variants=cfg.get("variants"),
                )
            else:
                durations = cfg.get("frame_durations", [100])
                state = AnimState(
                    name=name, anim_type=anim_type,
                    frames=frames, durations=durations,
                    loop=cfg.get("loop", True),
                    interruptible=cfg.get("interruptible", True),
                    exit_transition=cfg.get("exit_transition"),
                    variants=cfg.get("variants"),
                )

            self._states[name] = state

        if AnimationState.IDLE not in self._states:
            fallback = QPixmap(self._config.get("frame_width", 150),
                               self._config.get("frame_height", 150))
            fallback.fill()
            self._states[AnimationState.IDLE] = AnimState(
                name=AnimationState.IDLE, anim_type="simple",
                frames=[fallback], durations=[1000],
                loop=True, interruptible=True,
            )

    def get_current_state(self) -> AnimState:
        return self._states.get(self.current_state_name, self._states[AnimationState.IDLE])

    def get_current_pixmap(self) -> QPixmap:
        if self._transition_frames is not None:
            idx = min(self._transition_frame_index, len(self._transition_frames) - 1)
            return self._transition_frames[idx]

        state = self.get_current_state()
        if state.type == "composite":
            if state.current_sub_anim is None:
                self._pick_sub_animation(state)
            sa = state.current_sub_anim
            if sa:
                idx = min(self.current_frame_index, len(sa.frames) - 1)
                return sa.frames[idx]
            return self._fallback_pixmap()

        frames = state.active_frames
        if not frames:
            return self._fallback_pixmap()
        idx = min(self.current_frame_index, len(frames) - 1)
        return frames[idx]

    def _fallback_pixmap(self) -> QPixmap:
        from PySide6.QtGui import QPixmap as QP
        w = self._config.get("frame_width", 150)
        h = self._config.get("frame_height", 150)
        pix = QP(w, h)
        pix.fill()
        return pix

    def get_current_state_name(self) -> str:
        return self.current_state_name

    def request_state(self, state_name: str,
                      emotion_state: Optional[dict] = None) -> bool:
        if state_name not in self._states:
            logger.warning(f"Unknown state '{state_name}', ignoring")
            return False

        current = self.get_current_state()

        if current.name == state_name:
            return True

        if not current.interruptible and current.loop:
            self._queued_state = state_name
            self._queued_emotion = emotion_state
            return False

        self._apply_variant(state_name, emotion_state)
        transition_key = f"{current.name}_to_{state_name}"
        if transition_key not in self._transitions:
            transition_key = f"{state_name}_to_{current.name}"
        if transition_key in self._transitions:
            trans_cfg = self._transitions[transition_key]
            t_frames = trans_cfg.get("frames", [])
            t_durations = trans_cfg.get("frame_durations", [100])
            t_pixmaps = self._load_transition_frames(t_frames)
            if t_pixmaps:
                self._transition_frames = t_pixmaps
                self._transition_durations = t_durations
                self._transition_frame_index = 0
                self.frame_elapsed_ms = 0.0
                self._pending_state = state_name
                return True

        self._switch_now(state_name)
        return True

    def _apply_variant(self, state_name: str,
                       emotion_state: Optional[dict]):
        state = self._states.get(state_name)
        if not state or not state.variants or not emotion_state:
            return
        for vname, vcfg in state.variants.items():
            condition = vcfg.get("condition", {})
            if self._matches_condition(condition, emotion_state):
                v_frames = self._frames_cache.get(f"{state_name}/{vname}")
                if v_frames:
                    state.active_frames = v_frames
                    state.active_durations = vcfg.get("frame_durations",
                                                      state.durations)
                return

    def _matches_condition(self, condition: dict,
                           emotion_state: dict) -> bool:
        for var, (lo, hi) in condition.items():
            val = emotion_state.get(var, 0.5)
            if not (lo <= val <= hi):
                return False
        return True

    def _load_transition_frames(self, frame_refs: List[str]) -> List[QPixmap]:
        pixmaps = []
        for ref in frame_refs:
            pix = self._frames_cache.get(ref)
            if pix:
                pixmaps.extend(pix)
        return pixmaps

    def _switch_now(self, state_name: str):
        self.current_state_name = state_name
        self.current_frame_index = 0
        self.frame_elapsed_ms = 0.0
        self._queued_state = None
        self._queued_emotion = None

        state = self._states.get(state_name)

        if state and state.type == "composite" and state.sub_animations:
            self._pick_sub_animation(state)

    def force_state(self, state_name: str):
        if state_name not in self._states:
            return
        self._transition_frames = None
        self._pending_state = None
        self._one_shot_return = None
        self._queued_state = None
        self._queued_emotion = None
        self._switch_now(state_name)

    def update(self, dt_ms: float):
        scaled_dt = dt_ms * self._base_speed

        if self._transition_frames is not None:
            self._advance_transition(scaled_dt)
            return

        state = self.get_current_state()
        if state.type == "composite":
            self._advance_composite(state, scaled_dt)
        else:
            self._advance_simple(state, scaled_dt)

    def _advance_transition(self, dt_ms: float):
        self.frame_elapsed_ms += dt_ms
        duration = self._transition_durations[
            min(self._transition_frame_index, len(self._transition_durations) - 1)
        ]
        if self.frame_elapsed_ms >= duration:
            self.frame_elapsed_ms = 0.0
            self._transition_frame_index += 1
            if self._transition_frame_index >= len(self._transition_frames):
                self._transition_frames = None
                self._transition_durations = None
                self._transition_frame_index = 0
                if self._pending_state:
                    self._switch_now(self._pending_state)
                    self._pending_state = None

    def _advance_simple(self, state: AnimState, dt_ms: float):
        self.frame_elapsed_ms += dt_ms
        duration = state.active_durations[
            min(self.current_frame_index, len(state.active_durations) - 1)
        ]
        time_scale = max(0.01, self._base_speed)
        effective_duration = duration / time_scale

        if self.frame_elapsed_ms >= effective_duration:
            self.frame_elapsed_ms = 0.0
            self.current_frame_index += 1

            if self.current_frame_index >= len(state.active_frames):
                if state.type == "one_shot" and state.exit_transition and not state.loop:
                    self._switch_now(state.exit_transition)
                    return
                if state.loop:
                    self.current_frame_index = 0
                    self._check_queued()
                else:
                    self.current_frame_index = len(state.active_frames) - 1

    def _advance_composite(self, state: AnimState, dt_ms: float):
        if state.current_sub_anim is None:
            self._pick_sub_animation(state)
            return

        sa = state.current_sub_anim
        self.frame_elapsed_ms += dt_ms
        duration = sa.durations[
            min(self.current_frame_index, len(sa.durations) - 1)
        ]

        if self.frame_elapsed_ms >= duration:
            self.frame_elapsed_ms = 0.0
            self.current_frame_index += 1

            if self.current_frame_index >= len(sa.frames):
                if sa.loop:
                    self.current_frame_index = 0
                    self._check_queued()
                else:
                    self._pick_sub_animation(state)

    def _check_queued(self):
        if self._queued_state is not None:
            qs = self._queued_state
            qe = self._queued_emotion
            self._queued_state = None
            self._queued_emotion = None
            self.request_state(qs, qe)

    def _pick_sub_animation(self, state: AnimState):
        now = time.monotonic()
        available = [
            sa for sa in (state.sub_animations or [])
            if (now - sa.last_played) * 1000 >= sa.cooldown_ms
        ]
        if not available:
            available = state.sub_animations or []

        weights = [sa.weight for sa in available]
        chosen = random.choices(available, weights=weights, k=1)[0]
        chosen.last_played = now
        state.current_sub_anim = chosen
        self.current_frame_index = 0
        self.frame_elapsed_ms = 0.0
        self._composite_last_pick = now

    def set_frame_speed(self, multiplier: float):
        self._base_speed = max(0.01, multiplier)
