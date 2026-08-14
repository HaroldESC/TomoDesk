import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def suggest_memory_from_conversation(
    memory_manager, message_count_threshold: int = 15
) -> Optional[str]:
    recent = memory_manager.get_recent_messages(n=message_count_threshold)
    if len(recent) < message_count_threshold:
        return None

    if memory_manager.has_recent_suggestion(hours=1):
        return None

    return (
        "We've been talking for a while. Would you like me to remember anything "
        "from this conversation? You can use /remember <text> to save it."
    )


def detect_milestone_keywords(messages: List[Dict]) -> List[str]:
    keywords = [
        "terminé", "terminado", "completé", "completado", "logré",
        "finished", "completed", "done", "achieved",
        "empecé", "comencé", "inicié", "empezado", "comenzado",
        "started", "began", "launched",
        "aprendí", "descubrí", "aprendido",
        "learned", "discovered", "realized",
        "cambié", "migré", "actualicé",
        "switched", "migrated", "upgraded",
        "decidí", "decidido",
        "decided", "chose",
    ]

    milestones = []
    for msg in messages:
        content = msg.get("content", "").lower()
        for kw in keywords:
            if kw in content:
                milestones.append(msg.get("content", ""))
                break

    return milestones[:3]
