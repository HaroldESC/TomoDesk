from unittest.mock import MagicMock

import pytest

from src.core.conversation import ConversationEngine


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.generate.return_value = "Mock response"
    return p


@pytest.fixture
def mock_prompt_builder():
    pb = MagicMock()
    pb.build_messages.return_value = [
        {"role": "system", "content": "system msg"},
        {"role": "user", "content": "Hello"},
    ]
    return pb


@pytest.fixture
def mock_memory_manager():
    mm = MagicMock()
    return mm


def test_chat_stores_messages(mock_provider, mock_prompt_builder, mock_memory_manager):
    engine = ConversationEngine(
        mock_provider, mock_prompt_builder, mock_memory_manager, {}
    )
    result = engine.chat("Hello")

    assert result == "Mock response"
    mock_memory_manager.add_message.assert_any_call("user", "Hello")
    mock_memory_manager.add_message.assert_any_call("assistant", "Mock response")


def test_chat_stream_accumulates(mock_provider, mock_prompt_builder, mock_memory_manager):
    mock_provider.generate_stream.return_value = iter(["Hel", "lo", " world"])

    engine = ConversationEngine(
        mock_provider, mock_prompt_builder, mock_memory_manager, {}
    )
    tokens = list(engine.chat_stream("Hi"))

    assert "".join(tokens) == "Hello world"
    mock_memory_manager.add_message.assert_any_call("user", "Hi")
    mock_memory_manager.add_message.assert_any_call("assistant", "Hello world")
