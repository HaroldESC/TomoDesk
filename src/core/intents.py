"""Catálogo oficial de intenciones visuales de TomoDesk.

Las intenciones son el vocabulario semántico compartido entre los Context Packs
(que producen eventos) y los Sprite Packs (que deciden cómo representarlas).
El motor nunca pide una animación: siempre pide una intención.
"""

from enum import Enum
from typing import FrozenSet, Optional, Union


class VisualIntent(str, Enum):
    """Intenciones visuales oficiales del sistema."""

    IDLE = "IDLE"
    TALKING = "TALKING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SLEEPING = "SLEEPING"
    CELEBRATE = "CELEBRATE"
    SURPRISED = "SURPRISED"
    CONFUSED = "CONFUSED"
    WORKING_CODE = "WORKING_CODE"
    WORKING_ART = "WORKING_ART"
    READING = "READING"
    WRITING = "WRITING"
    GAMING = "GAMING"
    WAITING = "WAITING"
    LOOKING = "LOOKING"
    NOTIFICATION = "NOTIFICATION"


OFFICIAL_INTENTS: FrozenSet[VisualIntent] = frozenset(VisualIntent)


def normalize_intent(value: Union[str, VisualIntent, None]) -> Optional[VisualIntent]:
    """Normaliza un valor a un :class:`VisualIntent` o devuelve ``None``.

    Acepta miembros del enum, mayúsculas, minúsculas o mixto.
    """
    if isinstance(value, VisualIntent):
        return value
    if not isinstance(value, str):
        return None
    try:
        return VisualIntent(value.strip().upper())
    except ValueError:
        return None


def is_official(intent: Union[str, VisualIntent]) -> bool:
    """Indica si la intención pertenece al catálogo oficial."""
    normalized = normalize_intent(intent)
    return normalized is not None and normalized in OFFICIAL_INTENTS