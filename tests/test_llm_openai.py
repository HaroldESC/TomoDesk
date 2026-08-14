import pytest
from unittest.mock import Mock, patch

from src.llm.llm import LLMError, OpenAICompatibleProvider, create_provider


def test_create_openai_provider():
    config = {
        "llm": {
            "provider": "openai_compatible",
            "model": "test-model",
            "endpoint": "http://localhost:1234",
        }
    }
    provider = create_provider(config, api_key=None)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "test-model"


def test_openai_generate_mocked(mocker):
    mock_openai = mocker.patch("openai.OpenAI")
    mock_client = mock_openai.return_value
    mock_client.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Mocked response"))]
    )

    provider = OpenAICompatibleProvider("test", "http://localhost:1234")
    result = provider.generate([{"role": "user", "content": "Hi"}])
    assert result == "Mocked response"


def test_openai_generate_error(mocker):
    mock_openai = mocker.patch("openai.OpenAI")
    mock_client = mock_openai.return_value
    mock_client.chat.completions.create.side_effect = Exception("Connection refused")

    provider = OpenAICompatibleProvider("test", "http://localhost:9999")
    with pytest.raises(LLMError, match="Connection refused"):
        provider.generate([{"role": "user", "content": "Hi"}])


def test_openai_is_available_true(mocker):
    mock_openai = mocker.patch("openai.OpenAI")
    mock_client = mock_openai.return_value
    mock_client.models.list.return_value = Mock(
        data=[Mock(id="test-model"), Mock(id="other-model")]
    )

    provider = OpenAICompatibleProvider("test-model", "http://localhost:1234")
    assert provider.is_available() is True


def test_openai_is_available_false(mocker):
    mock_openai = mocker.patch("openai.OpenAI")
    mock_client = mock_openai.return_value
    mock_client.models.list.return_value = Mock(
        data=[Mock(id="other-model")]
    )

    provider = OpenAICompatibleProvider("missing-model", "http://localhost:1234")
    assert provider.is_available() is False


def test_openai_generate_stream_mocked(mocker):
    class MockChunk:
        def __init__(self, content):
            self.choices = [Mock(delta=Mock(content=content))]

    mock_openai = mocker.patch("openai.OpenAI")
    mock_client = mock_openai.return_value
    mock_client.chat.completions.create.return_value = [
        MockChunk("Hello"), MockChunk(" world"), MockChunk("!")
    ]

    provider = OpenAICompatibleProvider("test", "http://localhost:1234")
    result = "".join(list(provider.generate_stream([{"role": "user", "content": "Hi"}])))
    assert result == "Hello world!"
