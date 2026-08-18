"""Modelos declarativos del Sprite Pack (formato ``sprite-pack-v1``).

Separación de conceptos:

- **Intención** = qué quiere representar el agente (``src.core.intents``).
- **Clip** = cómo se ve: frames, timing, modo de reproducción.
- **Transición** = cómo cambia entre clips.
- **Overlay** = comportamiento simultáneo (parpadeo, bob, etc.).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ClipFrame:
    """Un frame de un clip con su duración propia."""

    file: str
    duration_ms: int


@dataclass
class AnimationClip:
    """Secuencia reproducible con timings declarativos.

    ``mode`` admite: ``loop``, ``once``, ``hold``, ``ping_pong``, ``timed``.
    """

    name: str
    mode: str
    frames: List[ClipFrame]
    interval_ms: int = 0
    return_to: Optional[str] = None
    interruptible: bool = True
    priority: int = 0
    transition_in_ms: int = 0
    transition_out_ms: int = 0
    overlays: List[str] = field(default_factory=list)
    variants: Dict[str, dict] = field(default_factory=dict)


@dataclass
class SpritePackData:
    """Manifest parseado de un Sprite Pack."""

    id: str
    name: str
    version: str
    assets: Dict[str, object]
    intent_map: Dict[str, str]
    fallbacks: Dict[str, str]
    clips: Dict[str, AnimationClip]
    transitions: Dict[str, dict] = field(default_factory=dict)