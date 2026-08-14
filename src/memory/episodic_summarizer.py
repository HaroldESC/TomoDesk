import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class EpisodicSummarizer:
    def __init__(self, memory_manager, llm_provider, config: Dict):
        self.memory_manager = memory_manager
        self.llm_provider = llm_provider
        self.config = config
        self.message_threshold = config.get("memory", {}).get("episodic_message_threshold", 15)
        self.importance_threshold = config.get("memory", {}).get("episodic_auto_threshold", 0.6)
        self._last_check_message_count = 0

    def should_check(self) -> bool:
        recent = self.memory_manager.get_recent_messages()
        current_count = len(recent)

        crossed = (current_count // self.message_threshold) > (self._last_check_message_count // self.message_threshold)

        if crossed:
            self._last_check_message_count = current_count
            return True
        return False

    def summarize_conversation(self) -> List[Dict]:
        recent = self.memory_manager.get_recent_messages(n=self.message_threshold * 2)

        if len(recent) < 10:
            logger.debug("Not enough messages to summarize")
            return []

        prompt = self._build_summarization_prompt(recent)

        try:
            messages = [
                {"role": "system", "content": "You are a memory summarizer. Extract key facts. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt},
            ]
            response = self.llm_provider.generate(messages)
            results = self._parse_summarization_response(response)
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return []

        stored = []
        for item in results:
            if item.get("importance_score", 0) >= self.importance_threshold:
                try:
                    self.memory_manager.add_episodic_memory(
                        summary=item["summary"],
                        importance_score=item["importance_score"],
                        source="auto",
                    )
                    item["stored"] = True
                    logger.info(f"Auto-saved episodic memory: {item['summary'][:80]}...")
                except Exception as e:
                    logger.error(f"Failed to store episodic memory: {e}")
                    item["stored"] = False
            else:
                item["stored"] = False
            stored.append(item)

        return stored

    def summarize_on_session_end(self) -> List[Dict]:
        recent = self.memory_manager.get_recent_messages()

        if len(recent) < 5:
            logger.debug("Session too short for summary")
            return []

        prompt = self._build_session_summary_prompt(recent)

        try:
            messages = [
                {"role": "system", "content": "You are a memory summarizer. Summarize the session in 1-3 key points. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt},
            ]
            response = self.llm_provider.generate(messages)
            results = self._parse_summarization_response(response)
        except Exception as e:
            logger.error(f"Session summarization failed: {e}")
            return []

        stored = []
        for item in results:
            if item.get("importance_score", 0) >= self.importance_threshold:
                try:
                    self.memory_manager.add_episodic_memory(
                        summary=item["summary"],
                        importance_score=item["importance_score"],
                        source="auto",
                    )
                    item["stored"] = True
                except Exception as e:
                    logger.error(f"Failed to store session memory: {e}")
                    item["stored"] = False
            else:
                item["stored"] = False
            stored.append(item)

        return stored

    def _build_summarization_prompt(self, messages: List[Dict]) -> str:
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in messages[-30:]
        ])

        prompt = f"""Analyze this conversation between a user and their desktop companion AI. 
Identify 1-3 key moments that seem important enough to remember long-term.

Important moments include:
- Goals or projects the user started or completed
- Personal preferences revealed by the user
- Significant decisions or changes mentioned
- Achievements or milestones
- Important dates or deadlines mentioned

Do NOT include:
- Casual greetings or small talk
- Vague or uncertain statements
- Things already obvious from context

Conversation:
{conversation_text}

Respond with a JSON array. Each element must have:
- "summary": A single concise sentence in the same language as the conversation.
- "importance_score": A float from 0.0 to 1.0 (0.8+ = major milestone, 0.6-0.8 = notable event, <0.6 = minor).

Example response:
[
  {{"summary": "User started a new Python project called TomoDesk", "importance_score": 0.85}},
  {{"summary": "User prefers dark mode for coding", "importance_score": 0.55}}
]

If nothing important happened, return an empty array: []
"""
        return prompt

    def _build_session_summary_prompt(self, messages: List[Dict]) -> str:
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content'][:150]}"
            for msg in messages[-50:]
        ])

        prompt = f"""Summarize this work session. Identify 1-3 key takeaways that someone should remember.

Session conversation:
{conversation_text}

Respond with a JSON array of objects with "summary" and "importance_score" (0.0-1.0).
Only include genuinely important information. If nothing notable happened, return [].
"""
        return prompt

    def _parse_summarization_response(self, response: str) -> List[Dict]:
        response = response.strip()

        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        try:
            data = json.loads(response)
            if isinstance(data, list):
                valid = []
                for item in data:
                    if isinstance(item, dict) and "summary" in item:
                        valid.append({
                            "summary": str(item["summary"]),
                            "importance_score": float(item.get("importance_score", 0.5)),
                        })
                return valid
            else:
                logger.warning(f"Expected JSON array, got: {type(data)}")
                return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse summarization response: {e}")
            logger.debug(f"Raw response: {response[:200]}")
            return []

    def reset_session_counter(self) -> None:
        self._last_check_message_count = 0
