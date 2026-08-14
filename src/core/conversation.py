import logging
import threading
from typing import Dict, Generator, List

from src.memory.episodic_utils import suggest_memory_from_conversation

logger = logging.getLogger(__name__)


class ConversationEngine:
    def __init__(self, provider, prompt_builder, memory_manager, config: Dict, state_manager=None, episodic_summarizer=None):
        self._provider = provider
        self._prompt_builder = prompt_builder
        self._memory_manager = memory_manager
        self._config = config
        self.state_manager = state_manager
        self.episodic_summarizer = episodic_summarizer

    def _update_emotional_state(self, user_input: str) -> Dict | None:
        if not self.state_manager:
            return None
        self.state_manager.update("user_message")

        user_lower = user_input.lower()
        positive_keywords = ["gracias", "thank", "eres genial", "me gusta", "buen trabajo",
                             "excelente", "perfecto", "te quiero", "me ayudaste"]
        if any(kw in user_lower for kw in positive_keywords):
            self.state_manager.update("positive_feedback")

        negative_keywords = ["no me gusta", "mal", "error", "equivocado", "no sirve", "inútil"]
        if any(kw in user_lower for kw in negative_keywords):
            self.state_manager.update("negative_feedback", intensity=0.5)

        recent = self._memory_manager.get_recent_messages(n=20)
        if len(recent) >= 15:
            self.state_manager.update("long_conversation", intensity=0.5)

        return self.state_manager.get_state()

    def _trigger_episodic_check(self) -> None:
        if self.episodic_summarizer and self.episodic_summarizer.should_check():
            logger.info("Triggering episodic summarization check...")
            threading.Thread(
                target=self.episodic_summarizer.summarize_conversation,
                daemon=True,
            ).start()

    def chat(self, user_input: str, emotional_state: Dict = None) -> str:
        emotional_state = self._update_emotional_state(user_input) or emotional_state
        messages = self._prompt_builder.build_messages(user_input, emotional_state, state_manager=self.state_manager)

        response = self._provider.generate(messages)
        self._memory_manager.add_message("user", user_input)
        self._memory_manager.add_message("assistant", response)

        suggestion = suggest_memory_from_conversation(self._memory_manager, message_count_threshold=15)
        if suggestion:
            response += f"\n\n{suggestion}"

        self._trigger_episodic_check()
        return response

    def chat_stream(
        self, user_input: str, emotional_state: Dict = None
    ) -> Generator[str, None, None]:
        emotional_state = self._update_emotional_state(user_input) or emotional_state
        messages = self._prompt_builder.build_messages(user_input, emotional_state, state_manager=self.state_manager)
        self._memory_manager.add_message("user", user_input)

        full_response = ""
        for token in self._provider.generate_stream(messages):
            full_response += token
            yield token

        self._memory_manager.add_message("assistant", full_response)

        suggestion = suggest_memory_from_conversation(self._memory_manager, message_count_threshold=15)
        if suggestion:
            yield f"\n\n{suggestion}"

        self._trigger_episodic_check()

    def summarize_session(self) -> List[Dict]:
        if self.episodic_summarizer:
            return self.episodic_summarizer.summarize_on_session_end()
        return []

    def check_availability(self) -> bool:
        return self._provider.is_available()
