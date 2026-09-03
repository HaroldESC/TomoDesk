from src.system.commands import cmd_model


def test_model_status_no_model(mock_i18n, tmp_path, mocker):
    mocker.patch("src.system.commands.download.model_exists", return_value=False)
    mocker.patch(
        "src.system.commands.download.model_path_from_config",
        return_value=tmp_path / "model.gguf",
    )
    mocker.patch("src.system.commands._llama_cpp_installed", return_value=True)
    msg, continue_loop = cmd_model("status", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.model_status_header" in msg
    assert "commands.model_status_download_hint" in msg


def test_model_status_present(mock_i18n, tmp_path, mocker):
    mocker.patch("src.system.commands.download.model_exists", return_value=True)
    mocker.patch(
        "src.system.commands.download.model_path_from_config",
        return_value=tmp_path / "model.gguf",
    )
    mocker.patch("src.system.commands._llama_cpp_installed", return_value=True)
    msg, _ = cmd_model("status", None, {}, i18n=mock_i18n)
    assert "commands.model_status_download_hint" not in msg


def test_model_download(mock_i18n, tmp_path, mocker):
    dest = tmp_path / "model.gguf"
    mocker.patch("src.system.commands.download.model_exists", side_effect=[False, True])
    mocker.patch(
        "src.system.commands.download.model_path_from_config", return_value=dest
    )
    mocker.patch(
        "src.system.commands.download.download_model", return_value=dest
    )
    msg, continue_loop = cmd_model("download", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.model_downloaded" in msg


def test_model_download_already_present(mock_i18n, mocker):
    mocker.patch("src.system.commands.download.model_exists", return_value=True)
    msg, _ = cmd_model("download", None, {}, i18n=mock_i18n)
    assert "commands.model_already_downloaded" in msg


def test_model_usage_hint(mock_i18n):
    msg, continue_loop = cmd_model("bogus", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.model_usage" in msg
