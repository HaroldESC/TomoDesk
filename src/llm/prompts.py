from typing import Dict, List


class PromptBuilder:
    def __init__(self, config: Dict, context_builder, memory_manager, i18n=None):
        self._config = config
        self._context_builder = context_builder
        self._memory_manager = memory_manager
        self._i18n = i18n

    def build_messages(
        self,
        user_input: str,
        emotional_state: Dict = None,
        include_memories: bool = True,
        state_manager=None,
    ) -> List[Dict[str, str]]:
        messages = []

        context = self._context_builder.build_context()
        system_content = (self._build_system_prompt(emotional_state, state_manager)
                          + "\n\n" + context)

        if include_memories:
            episodic = self._memory_manager.query_episodic(user_input, n=3)
            relevant_episodic = [m for m in episodic if m.get("distance", 0) < 1.5]
            if relevant_episodic:
                relevant_text = "\n".join([
                    f"- [{m.get('metadata', {}).get('timestamp', 'Unknown')}] {m.get('document', '')}"
                    for m in relevant_episodic
                ])
                system_content += f"\n\n[Important Memories]\n{relevant_text}"

            long_term = self._memory_manager.query_memories(user_input, n=3)
            relevant_lt = [m for m in long_term if m.get("distance", 0) < 1.5]
            if relevant_lt:
                lt_text = "\n".join([
                    f"- {m.get('document', '')}" for m in relevant_lt
                ])
                system_content += f"\n\n[Things I Know About You]\n{lt_text}"

            relevant_notes = self._memory_manager.search_notes_semantic(
                user_input, n=2
            )
            if relevant_notes:
                notes_text = "\n".join(
                    [
                        f"- Note: {n.get('metadata', {}).get('title', 'Untitled')}"
                        for n in relevant_notes
                    ]
                )
                system_content += f"\n\n[Relevant Notes]\n{notes_text}"

        messages.append({"role": "system", "content": system_content})

        history = self._memory_manager.get_recent_messages(n=10)
        messages.extend(history)

        messages.append({"role": "user", "content": user_input})

        return messages

    def build_proactive_prompt(
        self, trigger_description: str, emotional_state: Dict = None, state_manager=None
    ) -> List[Dict[str, str]]:
        messages = []

        context = self._context_builder.build_context()
        system_content = (self._build_system_prompt(emotional_state, state_manager)
                          + "\n\n" + context)

        messages.append({"role": "system", "content": system_content})

        history = self._memory_manager.get_recent_messages(n=10)
        messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": f"[You noticed: {trigger_description}. Make a brief, natural comment about this.]",
            }
        )

        return messages

    def _build_system_prompt(self, emotional_state: Dict = None, state_manager=None) -> str:
        if self._i18n:
            personality = self._config["personality"]
            name = personality.get("name", "Tomo")
            traits = personality.get("traits", "friendly, curious, helpful")

            happiness = 0.5
            energy = 0.5
            closeness = 0.5
            connection = 0.5

            if emotional_state is not None:
                happiness = emotional_state.get('happiness', 0.5)
                energy = emotional_state.get('energy', 0.5)
                closeness = emotional_state.get('closeness', 0.5)
                connection = emotional_state.get('connection', 0.5)

            prompt = self._i18n.t(
                "prompts.system",
                name=name,
                traits=traits,
                happiness=happiness,
                energy=energy,
                closeness=closeness,
                connection=connection,
                language=self._i18n.get_current_language(),
            )

            if state_manager is not None:
                instruction = state_manager.get_prompt_instruction()
                if instruction:
                    prompt += f"\n{instruction}"

            return prompt
        else:
            return self._context_builder.build_system_message(emotional_state, state_manager)
