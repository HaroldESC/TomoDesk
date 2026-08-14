import pytest

from src.llm.llm import OllamaProvider, create_provider


def test_create_ollama_provider():
    config = {
        "llm": {
            "provider": "ollama",
            "model": "llama3.2:1b",
            "endpoint": "http://localhost:11434",
        }
    }
    provider = create_provider(config, api_key=None)
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.2:1b"


def test_create_unknown_provider():
    config = {"llm": {"provider": "unknown", "model": "x"}}
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider(config)


def test_generate_mocked(mocker):
    mock_client = mocker.patch("src.llm.llm.ollama.Client")
    mock_client.return_value.chat.return_value = {
        "message": {"content": "Hello from mock!"}
    }
    provider = OllamaProvider(model="test-model")
    messages = [{"role": "user", "content": "Hi"}]
    result = provider.generate(messages)
    assert result == "Hello from mock!"


class _MockModel:
    def __init__(self, model_name):
        self.model = model_name


class _MockListResponse:
    def __init__(self, models):
        self.models = models


def test_is_available_true(mocker):
    mock_client = mocker.patch("src.llm.llm.ollama.Client")
    mock_client.return_value.list.return_value = _MockListResponse(
        [_MockModel("test-model:latest")]
    )
    provider = OllamaProvider(model="test-model")
    assert provider.is_available() is True


def test_is_available_false(mocker):
    mock_client = mocker.patch("src.llm.llm.ollama.Client")
    mock_client.return_value.list.return_value = _MockListResponse([])
    provider = OllamaProvider(model="test-model")
    assert provider.is_available() is False
