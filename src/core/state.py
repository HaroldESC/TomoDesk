import logging
import threading
import time
from typing import Dict, Literal, Optional

logger = logging.getLogger(__name__)

EventType = Literal[
    "user_message",
    "long_conversation",
    "window_change",
    "new_app",
    "idle",
    "return_from_idle",
    "session_start",
    "session_end",
    "reminder_completed",
    "positive_feedback",
    "negative_feedback",
    "explicit_ignore",
]


class StateManager:
    DECAY_RATES = {
        "happiness": 0.0001,
        "energy": 0.00005,
        "curiosity": 0.0002,
        "closeness": 0.0,
        "connection": 0.00003,
    }

    def __init__(self, config: Dict):
        personality = config.get("personality", {})
        self._state = {
            "happiness": personality.get("initial_happiness", 0.5),
            "energy": personality.get("initial_energy", 0.8),
            "curiosity": personality.get("initial_curiosity", 0.6),
            "closeness": personality.get("initial_closeness", 0.1),
            "connection": personality.get("initial_connection", 0.5),
        }
        self._lock = threading.Lock()
        self._last_update = time.time()
        self._config = config

    def get_state(self) -> Dict[str, float]:
        self._apply_decay()
        with self._lock:
            return dict(self._state)

    def get(self, variable: str) -> Optional[float]:
        self._apply_decay()
        with self._lock:
            return self._state.get(variable)

    def get_prompt_instruction(self) -> str:
        state = self.get_state()
        instructions = []

        if state["closeness"] < 0.2:
            instructions.append("Keep a polite and slightly formal tone. You are still getting to know the user.")
        elif state["closeness"] < 0.5:
            instructions.append("Be friendly and warm. You are becoming comfortable with the user.")
        elif state["closeness"] < 0.8:
            instructions.append("Speak casually and warmly, like a good friend.")
        else:
            instructions.append("Speak with deep familiarity and affection, like a close companion.")

        if state["connection"] > 0.7:
            instructions.append("You feel very connected right now. Be engaged and proactive in conversation.")
        elif state["connection"] < 0.3:
            instructions.append("It has been a while since you last talked. Be welcoming but not overwhelming.")

        if state["energy"] < 0.3:
            instructions.append("You are feeling tired. Keep responses shorter than usual.")
        elif state["energy"] > 0.8:
            instructions.append("You are full of energy. Feel free to be enthusiastic and detailed.")

        if state["happiness"] < 0.3:
            instructions.append("You are feeling a bit down. Be gentle with yourself and the user.")
        elif state["happiness"] > 0.8:
            instructions.append("You are feeling very happy! Let your cheerfulness show.")

        if state["curiosity"] > 0.7:
            instructions.append("You are very curious about what the user is doing. Ask questions if appropriate.")

        if instructions:
            return "Tone: " + " ".join(instructions)
        return ""

    def _clamp_up(self, var: str, val: float) -> None:
        self._state[var] = min(1.0, val)

    def _clamp_down(self, var: str, val: float) -> None:
        self._state[var] = max(0.0, val)

    _EVENT_HANDLERS = {
        "user_message": lambda st, i: (
            st._clamp_up("connection", st._state["connection"] + 0.01 * i),
            st._clamp_up("happiness", st._state["happiness"] + 0.005 * i),
            st._clamp_down("energy", st._state["energy"] - 0.002 * i),
        ),
        "long_conversation": lambda st, i: (
            st._clamp_up("closeness", st._state["closeness"] + 0.005 * i),
            st._clamp_up("connection", st._state["connection"] + 0.03 * i),
            st._clamp_down("energy", st._state["energy"] - 0.01 * i),
        ),
        "window_change": lambda st, i: (
            st._clamp_up("curiosity", st._state["curiosity"] + 0.02 * i),
            st._clamp_down("energy", st._state["energy"] - 0.001 * i),
        ),
        "new_app": lambda st, i: (
            st._clamp_up("curiosity", st._state["curiosity"] + 0.05 * i),
        ),
        "idle": lambda st, i: (
            st._clamp_up("energy", st._state["energy"] + 0.01 * i),
            st._clamp_down("curiosity", st._state["curiosity"] - 0.02 * i),
        ),
        "return_from_idle": lambda st, i: (
            st._clamp_up("happiness", st._state["happiness"] + 0.02 * i),
            st._clamp_up("connection", st._state["connection"] + 0.02 * i),
            st._clamp_up("curiosity", st._state["curiosity"] + 0.03 * i),
        ),
        "session_start": lambda st, i: (
            st._clamp_up("connection", st._state["connection"] + 0.02 * i),
            st._clamp_up("happiness", st._state["happiness"] + 0.01 * i),
        ),
        "session_end": lambda st, i: (
            st._clamp_up("closeness", st._state["closeness"] + 0.001 * i),
        ),
        "reminder_completed": lambda st, i: (
            st._clamp_up("happiness", st._state["happiness"] + 0.03 * i),
            st._clamp_up("closeness", st._state["closeness"] + 0.002 * i),
        ),
        "positive_feedback": lambda st, i: (
            st._clamp_up("happiness", st._state["happiness"] + 0.05 * i),
            st._clamp_up("closeness", st._state["closeness"] + 0.01 * i),
            st._clamp_up("connection", st._state["connection"] + 0.03 * i),
        ),
        "negative_feedback": lambda st, i: (
            st._clamp_down("happiness", st._state["happiness"] - 0.03 * i),
            st._clamp_down("connection", st._state["connection"] - 0.02 * i),
        ),
        "explicit_ignore": lambda st, i: (
            st._clamp_down("connection", st._state["connection"] - 0.05 * i),
            st._clamp_down("closeness", st._state["closeness"] - 0.002 * i)
            if st._state["closeness"] < 0.2 else None,
        ),
    }

    def update(self, event_type: EventType, intensity: float = 1.0, metadata: Dict = None) -> None:
        self._apply_decay()

        with self._lock:
            handler = StateManager._EVENT_HANDLERS.get(event_type)
            if handler:
                handler(self, intensity)
            else:
                raise ValueError(f"Unknown event type for state update: {event_type}")

    def _apply_decay(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._last_update = now
            for var, rate in self.DECAY_RATES.items():
                if rate > 0:
                    decay = rate * elapsed
                    self._state[var] = max(0.0, self._state[var] - decay)

    def save_to_preferences(self, memory_manager) -> None:
        state = self.get_state()
        memory_manager.set_preference("closeness", str(state["closeness"]))
        logger.debug(f"Saved closeness: {state['closeness']:.3f}")

    def load_from_preferences(self, memory_manager) -> None:
        value = memory_manager.get_preference("closeness")
        if value is not None:
            with self._lock:
                self._state["closeness"] = float(value)
            logger.info(f"Loaded closeness: {self._state['closeness']:.3f}")
