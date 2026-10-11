from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog, QWidget

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


@pytest.fixture(autouse=True)
def local_engine(mocker):
    """Mantiene el motor local disponible por defecto.

    El entorno de desarrollo puede tener o no ``llama-cpp-python`` instalado;
    los tests que simulan un binario sin motor local llaman al setter con
    ``False`` antes de construir el asistente.
    """
    patch = mocker.patch(
        "src.gui.windows.setup_wizard.is_llama_cpp_available",
        return_value=True,
    )

    def _set(available: bool):
        patch.return_value = available
        return patch

    return _set


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


class TestDialogStyle:
    """El asistente usa los mismos estilos que el resto de dialogos."""

    def test_missing_ui_config_uses_light_theme(self, qapp, mock_i18n, mocker):
        config = _config()
        config.pop("ui")
        spy = mocker.patch.object(sw, "get_style_set", wraps=sw.get_style_set)

        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            assert spy.call_args[0][0] == "light"
            assert wizard.styleSheet() == sw.get_style_set("light")["dialog"]
        finally:
            wizard.close()

    def test_configured_theme_is_respected(self, qapp, mock_i18n, mocker):
        config = _config()
        config["ui"]["theme"] = "dark"
        spy = mocker.patch.object(sw, "get_style_set", wraps=sw.get_style_set)

        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            assert spy.call_args[0][0] == "dark"
        finally:
            wizard.close()


class TestButtonStyles:
    """``Design.md`` §2.1: el boton primario no lleva objectName."""

    def test_primary_actions_have_no_object_name(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard._next_btn.objectName() == ""
            assert wizard._download_btn.objectName() == ""
        finally:
            wizard.close()

    def test_secondary_actions_keep_object_name(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard._cancel_btn.objectName() == "secondary"
            assert wizard._back_btn.objectName() == "secondary"
        finally:
            wizard.close()


class TestCentering:
    """``Design.md`` §5.3: el asistente se centra sobre su padre."""

    def test_centers_over_parent(self, qapp, mock_i18n):
        parent = QWidget()
        parent.setGeometry(240, 180, 900, 700)
        wizard = SetupWizard(_config(), i18n=mock_i18n, parent=parent)
        parent.show()
        try:
            wizard.show()
            qapp.processEvents()
            p = parent.geometry()
            assert wizard.pos().x() == p.x() + (p.width() - wizard.width()) // 2
            assert wizard.pos().y() == p.y() + (p.height() - wizard.height()) // 2
        finally:
            wizard.close()
            parent.close()


class TestCancel:
    """Cancelar siempre cierra, tambien con una descarga en curso."""

    def test_cancel_without_download_closes(self, qapp, mock_i18n):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            wizard.show()
            wizard._cancel_btn.click()
            qapp.processEvents()
            assert wizard.result() == QDialog.Rejected
            assert wizard.isVisible() is False
        finally:
            wizard.close()

    def test_cancel_during_download_closes_and_cancels(
        self, qapp, mock_i18n, mocker
    ):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        worker = mocker.MagicMock()
        worker.isRunning.return_value = True
        wizard._download_worker = worker
        try:
            wizard.show()
            wizard._on_cancel()
            qapp.processEvents()

            worker.request_cancel.assert_called()
            # Botones bloqueados y feedback visible mientras se cancela.
            assert wizard._cancel_btn.isEnabled() is False
            assert wizard._download_btn.isEnabled() is False
            assert wizard._status_label.text() == "Cancelling..."
            # El dialogo se cierra: el worker queda desparentado y vivo.
            assert wizard.result() == QDialog.Rejected
            assert wizard.isVisible() is False
            assert wizard._alive is False
            assert worker in sw._ORPHAN_WORKERS
        finally:
            sw._ORPHAN_WORKERS.discard(worker)
            wizard.close()

    def test_cancel_during_download_calls_reject_once(
        self, qapp, mock_i18n, mocker
    ):
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        worker = mocker.MagicMock()
        worker.isRunning.return_value = True
        wizard._download_worker = worker
        reject = mocker.patch.object(wizard, "reject")
        try:
            wizard._on_cancel()
            reject.assert_called_once()
        finally:
            sw._ORPHAN_WORKERS.discard(worker)
            wizard.close()

    def test_cancelling_text_comes_from_i18n(self, qapp, mocker):
        i18n = mocker.MagicMock()
        i18n.t.side_effect = lambda key, **kw: (
            "Cancelando..." if key == "setup.cancelling" else key
        )
        wizard = SetupWizard(_config(), i18n=i18n)
        worker = mocker.MagicMock()
        worker.isRunning.return_value = True
        wizard._download_worker = worker
        try:
            wizard._on_cancel()
            assert wizard._status_label.text() == "Cancelando..."
            i18n.t.assert_any_call("setup.cancelling")
        finally:
            sw._ORPHAN_WORKERS.discard(worker)
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


class TestLocalEngineAvailability:
    def test_absent_disables_local_and_defaults_to_later(
        self, qapp, mock_i18n, local_engine
    ):
        local_engine(False)
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard._local_radio.isEnabled() is False
            assert wizard._local_radio.isChecked() is False
            assert wizard._later_radio.isChecked() is True
            assert wizard.selected_mode() == MODE_LATER
            assert wizard._local_note is not None
            assert wizard._local_note.text() == (
                "Not available: this build does not include the local AI "
                "engine (llama.cpp)."
            )
            assert wizard._local_note.isHidden() is False
            assert wizard._local_note.wordWrap() is True
            mock_i18n.t.assert_any_call("setup.mode_local_unavailable")
        finally:
            wizard.close()

    def test_absent_apply_never_sets_llama_cpp(
        self, qapp, mock_i18n, local_engine, no_size_probe, mocker
    ):
        mocker.patch.object(sw, "save_config")
        local_engine(False)
        config = _config()
        wizard = SetupWizard(config, i18n=mock_i18n)
        try:
            # Forzar el modo local a mano: el radio esta deshabilitado para el
            # usuario, pero ``apply_to_config`` debe defenderse igualmente.
            wizard._local_radio.setChecked(True)
            assert wizard.selected_mode() == MODE_LOCAL
            wizard.apply_to_config()
            assert config["llm"]["provider"] != "llama_cpp"
            assert config["llm"]["provider"] == "ollama"
            assert config["setup"]["completed"] is True
            assert wizard.requires_restart() is False
        finally:
            wizard.close()

    def test_present_keeps_local_selected(self, qapp, mock_i18n, local_engine):
        local_engine(True)
        wizard = SetupWizard(_config(), i18n=mock_i18n)
        try:
            assert wizard._local_radio.isEnabled() is True
            assert wizard._local_radio.isChecked() is True
            assert wizard.selected_mode() == MODE_LOCAL
            assert wizard._local_note is None
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
