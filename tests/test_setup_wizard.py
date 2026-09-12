from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

from src.gui.windows import setup_wizard as sw
from src.gui.windows.setup_wizard import (
    MODE_EXTERNAL,
    MODE_LATER,
    MODE_LOCAL,
    SetupWizard,
    _DownloadWorker,
    format_size,
)


def _config():
    return {
        "llm": {
            "provider": "ollama",
            "model": "llama3.2:1b",
            "endpoint": "http://localhost:11434",
            "llama_cpp": {
                "model_file": "model.gguf",
                "model_path": "data/models/model.gguf",
            },
        },
        "ui": {"theme": "light"},
        "setup": {"completed": False},
    }


@pytest.fixture
def no_size_probe(mocker):
    return mocker.patch.object(sw, "_SizeWorker")


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512 B"

    def test_gigabytes(self):
        assert format_size(int(3.8 * 1024 ** 3)) == "3.8 GB"

    def test_unknown(self):
        assert format_size(-1) == ""
        assert format_size(None) == ""


class TestTranslateHelper:
    def test_forwards_kwargs_to_i18n(self, qapp, mocker):
        i18n = mocker.MagicMock()
        i18n.t.return_value = "Approximate size: 3 GB"
        wizard = SetupWizard(_config(), i18n=i18n)
        try:
            text = wizard._t("setup.local_size", "fallback", size="3 GB")
            assert text == "Approximate size: 3 GB"
            i18n.t.assert_any_call("setup.local_size", size="3 GB")
        finally:
            wizard.close()

    def test_formats_fallback_when_key_missing(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            text = wizard._t(
                "setup.local_size", "Approximate size: {size}", size="3 GB"
            )
            assert text == "Approximate size: 3 GB"
        finally:
            wizard.close()


class TestNavigation:
    def test_is_dialog(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert isinstance(wizard, QDialog)
        finally:
            wizard.close()

    def test_starts_on_welcome(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard._stack.currentIndex() == 0
            assert wizard._back_btn.isEnabled() is False
        finally:
            wizard.close()

    def test_default_mode_is_local(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard.selected_mode() == MODE_LOCAL
        finally:
            wizard.close()

    def test_welcome_to_mode(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._on_next()
            assert wizard._stack.currentIndex() == 1
            assert wizard._back_btn.isEnabled() is True
        finally:
            wizard.close()

    def test_local_selection_routes_to_download_page(
        self, qapp, mock_i18n, no_size_probe
    ):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._local_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            assert wizard._stack.currentIndex() == 2
        finally:
            wizard.close()

    def test_later_selection_routes_to_finish(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._later_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            assert wizard._stack.currentIndex() == 4
        finally:
            wizard.close()

    def test_back_from_mode_returns_to_welcome(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._on_next()
            wizard._on_back()
            assert wizard._stack.currentIndex() == 0
        finally:
            wizard.close()


class TestApply:
    def test_finish_local_applies_provider(self, qapp, mock_i18n, no_size_probe, mocker):
        mocker.patch.object(sw, "save_config")
        config = _config()
        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            wizard._local_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            wizard._on_next()
            assert wizard._stack.currentIndex() == 4
            wizard._on_next()
            assert config["llm"]["provider"] == "llama_cpp"
            assert config["setup"]["completed"] is True
            assert wizard.requires_restart() is True
            assert wizard.result() == QDialog.Accepted
        finally:
            wizard.close()

    def test_finish_external_applies_provider_and_key(self, qapp, mock_i18n, mocker):
        creds = mocker.patch.object(sw, "CredentialManager")
        mocker.patch.object(sw, "save_config")
        config = _config()
        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            wizard._external_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            wizard._endpoint_edit.setText("https://api.openai.com/v1")
            wizard._model_edit.setText("gpt-4o-mini")
            wizard._api_key_edit.setText("sk-test")
            wizard._on_next()
            assert wizard._stack.currentIndex() == 4
            wizard._on_next()
            assert config["llm"]["provider"] == "openai_compatible"
            assert config["llm"]["endpoint"] == "https://api.openai.com/v1"
            assert config["llm"]["model"] == "gpt-4o-mini"
            assert config["setup"]["completed"] is True
            creds.return_value.set_secret.assert_called_once_with(
                "llm_api_key", "sk-test"
            )
        finally:
            wizard.close()

    def test_invalid_external_endpoint_blocks(self, qapp, mock_i18n, mocker):
        mocker.patch.object(sw, "save_config")
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._external_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            wizard._endpoint_edit.setText("not-a-url")
            wizard._model_edit.setText("gpt-4o-mini")
            wizard._on_next()
            assert wizard._stack.currentIndex() == 3
            assert wizard._external_error != ""
        finally:
            wizard.close()

    def test_finish_later_keeps_provider(self, qapp, mock_i18n, mocker):
        mocker.patch.object(sw, "save_config")
        config = _config()
        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            wizard._later_radio.setChecked(True)
            wizard._on_next()
            wizard._on_next()
            wizard._on_next()
            assert config["llm"]["provider"] == "ollama"
            assert config["setup"]["completed"] is True
            assert wizard.requires_restart() is False
        finally:
            wizard.close()


class TestDownload:
    def test_start_download_marks_ready_when_present(
        self, qapp, mock_i18n, no_size_probe, mocker, tmp_path
    ):
        dest = tmp_path / "model.gguf"
        dest.write_bytes(b"gguf")
        mocker.patch(
            "src.llm.download.model_path_from_config", return_value=dest
        )
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard._start_download()
            assert wizard._local_ready is True
            assert wizard._download_worker is None
            assert wizard._download_btn.isEnabled() is False
        finally:
            wizard.close()

    def test_worker_emits_done(self, qapp, mocker):
        dest = Path("C:/x/model.gguf")
        mocker.patch(
            "src.llm.download.download_model",
            return_value=dest,
        )
        results = []
        worker = _DownloadWorker({})
        worker.done.connect(lambda d: results.append(d))
        worker.run()
        assert results == [str(dest)]

    def test_worker_emits_cancelled(self, qapp, mocker):
        from src.llm import download as dl

        def _boom(config, progress=None, should_cancel=None):
            raise dl.DownloadCancelled()

        mocker.patch.object(dl, "download_model", side_effect=_boom)
        errors = []
        worker = _DownloadWorker({})
        worker.error.connect(lambda e: errors.append(e))
        worker.run()
        assert errors == ["cancelled"]

    def test_worker_emits_error(self, qapp, mocker):
        mocker.patch(
            "src.llm.download.download_model",
            side_effect=RuntimeError("network down"),
        )
        errors = []
        worker = _DownloadWorker({})
        worker.error.connect(lambda e: errors.append(e))
        worker.run()
        assert errors == ["network down"]
