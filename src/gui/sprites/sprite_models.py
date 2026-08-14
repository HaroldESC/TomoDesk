from typing import Dict, List, Optional

from PySide6.QtGui import QPixmap


class SubAnimation:
    def __init__(self, name: str, frames: List[QPixmap],
                 durations: List[int], loop: bool,
                 weight: int, cooldown_ms: int):
        self.name = name
        self.frames = frames
        self.durations = durations
        self.loop = loop
        self.weight = weight
        self.cooldown_ms = cooldown_ms
        self.last_played: float = 0.0


class AnimState:
    def __init__(self, name: str, anim_type: str,
                 frames: List[QPixmap], durations: List[int],
                 loop: bool, interruptible: bool,
                 exit_transition: Optional[str] = None,
                 sub_animations: Optional[List[SubAnimation]] = None,
                 variants: Optional[dict] = None):
        self.name = name
        self.type = anim_type
        self.frames = frames
        self.durations = durations
        self.loop = loop
        self.interruptible = interruptible
        self.exit_transition = exit_transition
        self.sub_animations = sub_animations
        self.variants = variants or {}

        self.current_sub_anim: Optional[SubAnimation] = None
        self._variant_frames: Optional[List[QPixmap]] = None
        self._variant_durations: Optional[List[int]] = None

    @property
    def active_frames(self) -> List[QPixmap]:
        return self._variant_frames if self._variant_frames is not None else self.frames

    @active_frames.setter
    def active_frames(self, value: List[QPixmap]):
        self._variant_frames = value

    @property
    def active_durations(self) -> List[int]:
        return self._variant_durations if self._variant_durations is not None else self.durations

    @active_durations.setter
    def active_durations(self, value: List[int]):
        self._variant_durations = value

    def reset_variant(self):
        self._variant_frames = None
        self._variant_durations = None
