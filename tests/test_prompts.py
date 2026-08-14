from unittest.mock import MagicMock

import pytest

from src.llm.prompts import PromptBuilder


@pytest.fixture
def config():
    return {
        "personality": {
            "name": "Tomo",
            "traits": "friendly, curious, helpful",
        }
    }


@pytest.fixture
def mock_context_builder():
    cb = MagicMock()
    cb.build_system_message.return_value = "[System]\nYou are Tomo..."
    cb.build_context.return_value = "[Context]\nTime: 14:30\nActive window: Code"
    return cb


@pytest.fixture
def mock_memory_manager():
    mm = MagicMock()
    mm.get_recent_messages.return_value = []
    mm.query_episodic.return_value = []
    mm.query_memories.return_value = []
    return mm


def test_build_messages_basic(config, mock_context_builder, mock_memory_manager):
    builder = PromptBuilder(config, mock_context_builder, mock_memory_manager)
    messages = builder.build_messages("Hello", emotional_state={"happiness": 0.5})

    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Hello"


def test_build_messages_with_memories(config, mock_context_builder, mock_memory_manager):
    mock_memory_manager.query_episodic.return_value = [
        {"document": "User likes Python", "distance": 0.5}
    ]
    mock_memory_manager.query_memories.return_value = [
        {"document": "User prefers dark mode", "distance": 0.3}
    ]

    builder = PromptBuilder(config, mock_context_builder, mock_memory_manager)
    messages = builder.build_messages("test query")

    assert "[Important Memories]" in messages[0]["content"]
    assert "User likes Python" in messages[0]["content"]
    assert "[Things I Know About You]" in messages[0]["content"]
    assert "User prefers dark mode" in messages[0]["content"]


def test_build_messages_without_memories(config, mock_context_builder, mock_memory_manager):
    mock_memory_manager.query_episodic.return_value = [
        {"document": "User likes Python"}
    ]

    builder = PromptBuilder(config, mock_context_builder, mock_memory_manager)
    messages = builder.build_messages("test query", include_memories=False)

    assert "[Important Memories]" not in messages[0]["content"]


def test_build_proactive_prompt(config, mock_context_builder, mock_memory_manager):
    builder = PromptBuilder(config, mock_context_builder, mock_memory_manager)
    messages = builder.build_proactive_prompt("User opened Spotify")

    assert messages[-1]["role"] == "user"
    assert "You noticed: User opened Spotify" in messages[-1]["content"]
