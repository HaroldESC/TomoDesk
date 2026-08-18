"""VisualStateResolver: traduce eventos y estado del agente a intenciones visuales.

No conoce sprites ni clips: solo combina tres fuentes por prioridad
(agente > contexto > idle) y devuelve un :class:`VisualIntent`.
"""

from dataclasses import dataclass
from typing import Optional

from src.core.intents import VisualIntent, normalize_intent

AGENT_PRIORITY = 100


@dataclass
class IntentRequest:
    """Petición de intención producida por un Context Pack o el agente."""

    intent: VisualIntent
    priority: int
    source: str
    one_shot: bool = False


class VisualStateResolver:
    """Combina el intent del agente y los eventos de contexto en un intent único."""

    def __init__(self, context_manager=None):
        self._context = context_manager
        self._agent_intent: Optional[VisualIntent] = None
        self._base: Optional[IntentRequest] = None
        self._transient: Optional[IntentRequest] = None

    def set_agent_intent(self, intent: Optional[VisualIntent]) -> None:
        """Fija el intent de alta prioridad del agente (``None`` lo libera)."""
        self._agent_intent = normalize_intent(intent)

    def push_event(self, event: str, payload: Optional[dict] = None) -> None:
        """Alimenta un evento de sistema/app al resolver vía los Context Packs."""
        if self._context is None:
            return

        request = self._context.resolve_event(event, payload)

        if event == "app.foreground":
            self._base = None
            if request is not None:
                self._apply(request)
            return

        if request is not None:
            self._apply(request)

    def _apply(self, request: IntentRequest) -> None:
        if request.one_shot:
            self._transient = request
        else:
            self._base = request

    def resolve(self, emotion_state: Optional[dict] = None) -> VisualIntent:
        """Devuelve la intención visual vigente según prioridad."""
        if self._agent_intent is not None:
            return self._agent_intent
        if self._transient is not None and (
            self._base is None or self._transient.priority >= self._base.priority
        ):
            return self._transient.intent
        if self._base is not None:
            return self._base.intent
        return VisualIntent.IDLE

    @property
    def base_intent(self) -> Optional[VisualIntent]:
        """Intención base vigente (contexto), o ``None``."""
        return self._base.intent if self._base is not None else None

    # ── Ciclo de vida de one-shots (usado por SpriteManager) ─────────────

    def has_transient(self) -> bool:
        return self._transient is not None

    def transient_intent(self) -> Optional[VisualIntent]:
        return self._transient.intent if self._transient is not None else None

    def clear_transient(self) -> None:
        self._transient = None