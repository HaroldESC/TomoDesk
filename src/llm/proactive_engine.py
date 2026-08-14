import logging
import random
import threading
from typing import Dict, Optional

from src.personality.comment_loader import CommentLoader
from src.memory.memory import MemoryManager
from src.llm.proactive_policy import ProactivePolicy

logger = logging.getLogger(__name__)


class ProactiveEngine:
    def __init__(
        self,
        comment_loader: CommentLoader,
        policy: ProactivePolicy,
        memory_manager: MemoryManager,
        config: Dict,
        pack_manager=None,
    ):
        self.comment_loader = comment_loader
        self.policy = policy
        self.memory_manager = memory_manager
        self.config = config
        self.pack_manager = pack_manager
        self._on_comment_callback = None
        self._random_timer_thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()

    def set_delivery_callback(self, callback):
        self._on_comment_callback = callback

    def handle_trigger(
        self, trigger_type: str, context: Dict = None
    ) -> Optional[str]:
        logger.debug("handle_trigger called: type=%s", trigger_type)
        if not self.policy.can_comment(trigger_type):
            logger.debug("Trigger '%s' suppressed by policy", trigger_type)
            return None

        replacements = {
            "name": self.config.get("personality", {}).get("name", "Tomo")
        }
        if context:
            replacements.update(context)

        phrase = None
        if self.pack_manager:
            logger.debug("Pack manager available, active=%s, packs=%s",
                         self.pack_manager._active_pack,
                         list(self.pack_manager._packs.keys()))
            pack_phrases = self.pack_manager.get_phrases(trigger_type)
            logger.debug("get_phrases(%s) returned: %s", trigger_type,
                         f"{len(pack_phrases)} phrases" if pack_phrases else "None")
            if pack_phrases:
                phrase = random.choice(pack_phrases)
                if phrase:
                    try:
                        phrase = phrase.format(**replacements)
                    except KeyError:
                        pass
        else:
            logger.debug("No pack manager available")

        if phrase is None:
            if not self.comment_loader.has_category(trigger_type):
                logger.debug("No phrases for trigger '%s'", trigger_type)
                return None
            phrase = self.comment_loader.get_random(trigger_type, replacements)
        if phrase is None:
            return None

        self.policy.record_comment()

        self.memory_manager.log_interaction(
            "proactive_comment",
            {"trigger": trigger_type, "comment": phrase, "context": context or {}},
        )

        if self._on_comment_callback:
            self._on_comment_callback(phrase, trigger_type)

        logger.info("Proactive comment [%s]: %s", trigger_type, phrase)
        return phrase

    def start_random_timer(self) -> None:
        self._running = True
        self._stop_event.clear()
        self._random_timer_thread = threading.Thread(
            target=self._random_loop, daemon=True
        )
        self._random_timer_thread.start()
        logger.info("Random comment timer started")

    def stop_random_timer(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._random_timer_thread:
            self._random_timer_thread.join(timeout=1)
        logger.info("Random comment timer stopped")

    def _random_loop(self) -> None:
        while not self._stop_event.is_set():
            if not self._stop_event.is_set():
                self.handle_trigger("random")
            for _ in range(120):
                if self._stop_event.wait(1):
                    return

    def get_stats(self) -> Dict:
        return self.policy.get_stats()
