from unittest.mock import MagicMock

import pytest

from src.llm import download


def test_default_model_repo_is_public_mirror():
    assert download.DEFAULT_MODEL_REPO == "bartowski/Llama-3.2-1B-Instruct-GGUF"
    assert download.DEFAULT_MODEL_FILE == "Llama-3.2-1B-Instruct-Q4_K_M.gguf"


def test_default_url_uses_public_mirror():
    url = download.model_url_from_config({})
    assert url == (
        "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/"
        "resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
    )


def test_download_file_gated_repo_raises_friendly_error(tmp_path, mocker):
    from urllib.error import HTTPError

    err = HTTPError("https://example.com/m.gguf", 401, "Unauthorized", None, None)
    mocker.patch.object(download.urllib.request, "urlopen", side_effect=err)
    with pytest.raises(ValueError, match="autenticacion"):
        download.download_file("https://example.com/m.gguf", tmp_path / "m.gguf")


def test_download_file_not_found_raises_friendly_error(tmp_path, mocker):
    from urllib.error import HTTPError

    err = HTTPError("https://example.com/m.gguf", 404, "Not Found", None, None)
    mocker.patch.object(download.urllib.request, "urlopen", side_effect=err)
    with pytest.raises(ValueError, match="404"):
        download.download_file("https://example.com/m.gguf", tmp_path / "m.gguf")


class _FakeResp:
    def __init__(self, chunks, total):
        self.headers = {"Content-Length": str(total)}
        self._chunks = list(chunks)
        self._i = 0
        self._closed = False

    def read(self, size=-1):
        if self._i >= len(self._chunks):
            return b""
        chunk = self._chunks[self._i]
        self._i += 1
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._closed = True
        return False


def test_download_file_writes_and_progress(tmp_path, mocker):
    data = b"x" * 100
    chunks = [data[:45], data[45:]]
    resp = _FakeResp(chunks, len(data))
    mocker.patch.object(download.urllib.request, "urlopen", return_value=resp)

    dest = tmp_path / "model.gguf"
    calls = []
    result = download.download_file("https://example.com/model.gguf", dest, progress=lambda d, t: calls.append((d, t)))

    assert result == dest
    assert dest.read_bytes() == data
    assert calls[-1] == (100, 100)
    assert resp._closed is True
    # No leftover .part file
    assert not (tmp_path / "model.gguf.part").exists()


def test_download_file_uses_part_then_renames(tmp_path, mocker):
    data = b"prefix" + b"!" * 20
    resp = _FakeResp([data], len(data))
    mocker.patch.object(download.urllib.request, "urlopen", return_value=resp)

    dest = tmp_path / "model.gguf"
    # pre-existing corrupt destination shouldn't be touched until rename
    dest.write_bytes(b"corrupt")
    download.download_file("https://example.com/model.gguf", dest)
    assert dest.read_bytes() == data


def test_download_file_urlopen_uses_timeout_default(tmp_path, mocker):
    data = b"x" * 10
    resp = _FakeResp([data], len(data))
    mocker.patch.object(download.urllib.request, "urlopen", return_value=resp)

    dest = tmp_path / "model.gguf"
    download.download_file("https://example.com/model.gguf", dest)

    _, kwargs = download.urllib.request.urlopen.call_args
    assert kwargs["timeout"] == 30


def test_download_file_urlopen_propagates_explicit_timeout(tmp_path, mocker):
    data = b"x" * 10
    resp = _FakeResp([data], len(data))
    mocker.patch.object(download.urllib.request, "urlopen", return_value=resp)

    dest = tmp_path / "model.gguf"
    download.download_file("https://example.com/model.gguf", dest, timeout=5)

    _, kwargs = download.urllib.request.urlopen.call_args
    assert kwargs["timeout"] == 5


def test_model_exists(tmp_path):
    model = tmp_path / "model.gguf"
    config = {"llm": {"llama_cpp": {"model_path": str(model)}}}
    assert download.model_exists(config) is False
    model.write_bytes(b"gguf")
    assert download.model_exists(config) is True


def test_model_path_from_config_relative_uses_user_data(monkeypatch, tmp_path):
    monkeypatch.setattr(download.paths, "user_data_dir", lambda: tmp_path)
    config = {"llm": {"llama_cpp": {"model_path": "data/models/m.gguf"}}}
    path = download.model_path_from_config(config)
    assert path == tmp_path / "data/models/m.gguf"


def test_download_model_skips_if_exists(tmp_path, mocker):
    model = tmp_path / "m.gguf"
    model.write_bytes(b"gguf")
    config = {"llm": {"llama_cpp": {"model_path": str(model)}}}
    spy = mocker.spy(download, "download_file")
    result = download.download_model(config)
    assert result == model
    spy.assert_not_called()


def test_download_model_fetches_when_missing(tmp_path, mocker):
    model = tmp_path / "m.gguf"
    data = b"ggufdata"
    resp = _FakeResp([data], len(data))
    mocker.patch.object(download.urllib.request, "urlopen", return_value=resp)
    config = {"llm": {"llama_cpp": {"model_path": str(model)}}}
    result = download.download_model(config)
    assert result == model
    assert model.read_bytes() == data
