import pytest

from src.llm.llm import LLMError, create_provider
from src.llm.llama_cpp import LlamaCppProvider


def test_create_llama_cpp_provider(mocker, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    config = {
        "llm": {
            "provider": "llama_cpp",
            "llama_cpp": {"model_path": str(model), "n_ctx": 2048},
        }
    }
    import sys
    sys.modules["llama_cpp"] = mocker.MagicMock()
    try:
        provider = create_provider(config, api_key=None)
    finally:
        sys.modules.pop("llama_cpp", None)
    assert isinstance(provider, LlamaCppProvider)
    assert provider.n_ctx == 2048


def test_is_available_true_when_lib_and_model(mocker, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    mocker.patch.dict("sys.modules", {"llama_cpp": mocker.MagicMock()})
    provider = LlamaCppProvider(model_path=model)
    assert provider.is_available() is True
    assert provider._llm is not None


def test_is_available_false_when_lib_missing(mocker, tmp_path):
    import builtins
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "llama_cpp":
            raise ImportError("no llama_cpp")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=fake_import)
    provider = LlamaCppProvider(model_path=model)
    assert provider.is_available() is False
    with pytest.raises(LLMError, match="no esta instalado"):
        provider.generate([{"role": "user", "content": "Hi"}])


def test_is_available_false_when_model_file_missing(mocker):
    mocker.patch.dict("sys.modules", {"llama_cpp": mocker.MagicMock()})
    provider = LlamaCppProvider(model_path="does/not/exist.gguf")
    assert provider.is_available() is False


def test_generate_mocked(mocker, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    mocker.patch.dict("sys.modules", {"llama_cpp": mocker.MagicMock()})
    provider = LlamaCppProvider(model_path=model)
    provider._load()
    provider._llm.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "Hello from llama"}}]
    }
    result = provider.generate([{"role": "user", "content": "Hi"}])
    assert result == "Hello from llama"
    provider._llm.create_chat_completion.assert_called_once()


def test_generate_stream_mocked(mocker, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")
    mocker.patch.dict("sys.modules", {"llama_cpp": mocker.MagicMock()})
    provider = LlamaCppProvider(model_path=model)
    provider._llm = mocker.MagicMock()
    provider._llm.create_chat_completion.return_value = [
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        {"choices": [{"delta": {"content": ""}}]},
    ]
    result = "".join(provider.generate_stream([{"role": "user", "content": "Hi"}]))
    assert result == "Hello world"


def test_generate_error_when_not_available(mocker, tmp_path):
    import builtins
    model = tmp_path / "model.gguf"
    model.write_bytes(b"gguf")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "llama_cpp":
            raise ImportError("no llama_cpp")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=fake_import)
    provider = LlamaCppProvider(model_path=model)
    with pytest.raises(LLMError):
        list(provider.generate_stream([{"role": "user", "content": "Hi"}]))
