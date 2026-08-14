from datetime import datetime
from typing import Dict

from src.memory.memory import MemoryManager


class ContextBuilder:
    def __init__(self, config: Dict, memory_manager: MemoryManager, event_monitor=None):
        self._config = config
        self._memory_manager = memory_manager
        self._event_monitor = event_monitor

    def build_context(self) -> str:
        snapshot = self._event_monitor.get_latest() if self._event_monitor else None

        if snapshot is None:
            active_window = "Unknown"
            idle_time_seconds = 0
            cpu_percent = 0.0
            ram_percent = 0.0
        else:
            active_window = snapshot.get("active_window", "Unknown")
            idle_time_seconds = snapshot.get("idle_time_seconds", 0)
            cpu_percent = snapshot.get("cpu_percent", 0.0)
            ram_percent = snapshot.get("ram_percent", 0.0)

        time_str = datetime.now().strftime("%H:%M")
        idle_minutes = idle_time_seconds // 60
        idle_seconds = idle_time_seconds % 60

        monitoring_enabled = bool(
            self._config.get("privacy", {}).get("monitor_active_window", True)
        )
        if not monitoring_enabled:
            active_window = "Unknown"

        lines = [
            "[Context]",
            f"Time: {time_str}",
        ]
        if monitoring_enabled:
            lines.append(f"Active window: {active_window}")
        lines.extend([
            f"Idle: {idle_minutes}m {idle_seconds}s",
            f"System: CPU {cpu_percent}%, RAM {ram_percent}%",
            "Rules:",
        ])
        return "\n".join(lines)

    def build_system_message(self, emotional_state: Dict = None, state_manager=None) -> str:
        personality = self._config["personality"]
        name = personality.get("name", "Tomo")
        traits = personality.get("traits", "friendly, curious, helpful")

        lines = [
            "[System]",
            f"You are {name}, a desktop companion. Your personality is {traits}.",
            "Rules:",
        ]

        if emotional_state is not None:
            state_line = (
                f"Emotional state: happiness={emotional_state.get('happiness', 0.5)}, "
                f"energy={emotional_state.get('energy', 0.5)}, "
                f"curiosity={emotional_state.get('curiosity', 0.5)}, "
                f"closeness={emotional_state.get('closeness', 0.5)}, "
                f"connection={emotional_state.get('connection', 0.5)}."
            )
            lines.append(state_line)

            if state_manager is not None:
                instruction = state_manager.get_prompt_instruction()
                if instruction:
                    lines.append(instruction)

        return "\n".join(lines)
