import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QMessageBox, QSizePolicy

from src.context.context_pack import ContextPackManager
from src.platform import PlatformCapabilities, _set_platform


@pytest.fixture
def mock_config():
    return {
        "personality": {"name": "Tomo", "traits": "friendly, curious"},
        "llm": {"model": "llama3.2:1b", "endpoint": "http://localhost:11434"},
        "modes": {},
        "context": {"directory": "data/context_packs", "active_packs": ["vscode"]},
    }


@pytest.fixture(autouse=True)
def ensure_qapp(qapp):
    return qapp


@pytest.fixture
def inject_platform():
    """Inject a fake platform adapter; full capabilities unless overridden."""
    def _inject(**overrides):
        values = {
            "platform": "test",
            "window_enumeration": True,
            "idle_time": True,
            "taskbar_detection": True,
            "taskbar_entry": True,
            "open_path": True,
        }
        values.update(overrides)
        adapter = MagicMock()
        adapter.capabilities = PlatformCapabilities(**values)
        _set_platform(adapter)
        return adapter
    yield _inject
    _set_platform(None)


def _make_dialog(qtbot, config, mock_i18n, context_manager=None, proactive_engine=None):
    from src.gui.windows.settings_dialog import SettingsDialog
    dialog = SettingsDialog(
        config, proactive_engine, i18n=mock_i18n, context_manager=context_manager
    )
    qtbot.addWidget(dialog)
    return dialog


def _group_texts(page):
    return [
        g.property("_search_text")
        for g in page.findChildren(QGroupBox)
        if g.property("_search_text")
    ]


class TestSettingsNavigation:
    def test_sidebar_has_six_categories(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog._nav.count() == 6

    def test_switching_page_updates_stack(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._nav.setCurrentRow(2)
        assert dialog._stack.currentIndex() == 2
        dialog._nav.setCurrentRow(5)
        assert dialog._stack.currentIndex() == 5

    def test_packs_page_has_three_groups(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        texts = _group_texts(dialog._pages[1])
        assert len(texts) == 3
        assert "dialogs.settings.character_sprite" in texts
        assert "dialogs.settings.character_packs" in texts
        assert "dialogs.settings.packs_context" in texts

    def test_character_page_has_identity_only(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        texts = _group_texts(dialog._pages[2])
        assert len(texts) == 2
        assert "dialogs.settings.character_personality" in texts
        assert "dialogs.settings.character_mood" in texts


class TestSettingsSearch:
    def test_search_filters_groups(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._nav.setCurrentRow(0)
        dialog._search_field.setText("bubble")
        visible = [g for g in dialog._pages[0].findChildren(QGroupBox)
                   if g.property("_search_text") and not g.isHidden()]
        assert len(visible) == 1
        assert "bubble" in visible[0].property("_search_text")

    def test_search_no_results_label(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("zzzzz_no_match")
        assert not dialog._no_results_label.isHidden()
        dialog._search_field.setText("")
        assert dialog._no_results_label.isHidden()

    def test_search_clears_restores_all(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("bubble")
        dialog._search_field.setText("")
        page = dialog._pages[0]
        hidden = [g for g in page.findChildren(QGroupBox)
                  if g.property("_search_text") and g.isHidden()]
        assert len(hidden) == 0


class TestSettingsNavSizing:
    def test_nav_width_fits_content(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        hint = dialog._nav.sizeHintForColumn(0)
        assert hint > 0
        assert dialog._nav.minimumWidth() >= min(300, hint)

    def test_nav_uses_all_vertical_space(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert (
            dialog._nav.sizePolicy().verticalPolicy()
            == QSizePolicy.Policy.Expanding
        )
        assert (
            dialog._nav.horizontalScrollBarPolicy()
            == Qt.ScrollBarAlwaysOff
        )


class TestAdvancedLogs:
    def test_debug_prompts_checkbox_defaults_off(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert not dialog.debug_prompts.isChecked()

    def test_debug_prompts_checkbox_reads_config(self, qtbot, mock_config, mock_i18n):
        mock_config["logs"] = {"debug_prompts": True}
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.debug_prompts.isChecked()

    def test_debug_prompts_checkbox_saved(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.debug_prompts.setChecked(True)
        dialog._save_advanced()
        assert mock_config["logs"]["debug_prompts"] is True


class TestContextPacks:
    @staticmethod
    def _write_pack(directory: Path, pack_id: str):
        manifest = {
            "id": pack_id,
            "name": pack_id.title(),
            "version": "1.0.0",
            "format": "context-pack-v1",
            "app": pack_id,
            "events": {"app.foreground": {"intent": "WORKING_CODE", "priority": 1}},
        }
        pack_dir = directory / pack_id
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def _config(self, tmp_path):
        return {
            "personality": {"name": "Tomo", "traits": "x"},
            "llm": {"model": "m", "endpoint": "http://localhost:1"},
            "modes": {},
            "context": {"directory": str(tmp_path), "active_packs": ["vscode"]},
        }

    def test_list_shows_packs_and_save_applies(self, qtbot, mock_i18n, tmp_path):
        self._write_pack(tmp_path, "vscode")
        self._write_pack(tmp_path, "blender")
        config = self._config(tmp_path)
        cm = ContextPackManager(config, str(tmp_path))
        dialog = _make_dialog(qtbot, config, mock_i18n, context_manager=cm)
        assert dialog.context_pack_list.count() == 2

        checks = {
            dialog.context_pack_list.item(i).data(Qt.UserRole):
                dialog.context_pack_list.item(i).checkState()
            for i in range(dialog.context_pack_list.count())
        }
        assert checks["vscode"] == Qt.Checked
        assert checks["blender"] == Qt.Unchecked

        for i in range(dialog.context_pack_list.count()):
            item = dialog.context_pack_list.item(i)
            if item.data(Qt.UserRole) == "vscode":
                item.setCheckState(Qt.Unchecked)
            elif item.data(Qt.UserRole) == "blender":
                item.setCheckState(Qt.Checked)
        dialog._save_context()
        assert config["context"]["active_packs"] == ["blender"]
        active = [p["id"] for p in cm.list_packs() if p["active"]]
        assert active == ["blender"]

    def test_delete_pack(self, qtbot, mock_i18n, tmp_path):
        self._write_pack(tmp_path, "vscode")
        config = self._config(tmp_path)
        cm = ContextPackManager(config, str(tmp_path))
        dialog = _make_dialog(qtbot, config, mock_i18n, context_manager=cm)
        dialog.context_pack_list.setCurrentRow(0)
        with patch("src.gui.windows.settings_dialog.QMessageBox") as mb:
            mb.Yes = QMessageBox.StandardButton.Yes
            mb.No = QMessageBox.StandardButton.No
            mb.question.return_value = QMessageBox.StandardButton.Yes
            dialog._on_delete_context_pack()
        assert not (tmp_path / "vscode").exists()
        assert dialog.context_pack_list.count() == 0

    def test_creates_own_manager_when_none(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert isinstance(dialog.context_manager, ContextPackManager)


class TestModelDownload:
    def test_worker_is_persisted_on_dialog_and_reenables_button(
        self, qtbot, mock_config, mock_i18n, tmp_path
    ):
        from src.gui.windows import settings_dialog as sd

        dest = Path(str(tmp_path)) / "models" / "test.gguf"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        with patch("src.llm.download.model_path_from_config", return_value=dest), \
             patch.object(sd._ModelDownloadWorker, "start") as start_mock:
            dialog._on_download_model()

            worker = dialog._download_worker
            assert worker is not None
            assert worker.parent() is dialog
            assert not dialog.llama_download_btn.isEnabled()
            start_mock.assert_called_once()

            worker.finished.emit()

        assert dialog.llama_download_btn.isEnabled()

    def test_language_set_flag_persists_explicit_choice(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog.ui_lang.setCurrentText("es")
        dialog._save_appearance()
        assert "ui" in mock_config
        assert mock_config["ui"]["language"] == "es"
        assert mock_config["ui"]["language_set"] is True

        dialog.ui_lang.setCurrentText("auto")
        dialog._save_appearance()
        assert mock_config["ui"]["language"] == "auto"
        assert mock_config["ui"]["language_set"] is False

    def test_abort_download_safe_when_worker_deleted(
        self, qtbot, mock_config, mock_i18n, tmp_path
    ):
        from src.gui.windows import settings_dialog as sd

        dest = Path(str(tmp_path)) / "models" / "test.gguf"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        with patch("src.llm.download.model_path_from_config", return_value=dest), \
             patch.object(sd._ModelDownloadWorker, "start"):
            dialog._on_download_model()

        worker = dialog._download_worker
        worker.isRunning = MagicMock(
            side_effect=RuntimeError("libshiboken: Internal C++ object deleted")
        )
        dialog._abort_download()  # must not raise

    def test_done_message_uses_wordwrap_and_soft_breaks(
        self, qtbot, mock_config, mock_i18n, tmp_path
    ):
        from src.gui.windows import settings_dialog as sd

        dest = Path(str(tmp_path)) / "models" / "test.gguf"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        mb_class = MagicMock()
        mb_class.Information = 1

        with patch("src.llm.download.model_path_from_config", return_value=dest), \
             patch.object(sd._ModelDownloadWorker, "start"), \
             patch("src.gui.windows.settings_dialog.QMessageBox", mb_class):
            dialog._on_download_model()
            worker = dialog._download_worker
            worker.done.emit(dest)

        instance = mb_class.return_value
        label = instance.findChild.return_value
        assert label.setWordWrap.called
        assert label.setWordWrap.call_args[0][0] is True
        assert instance.setText.called
        assert dialog.llm_provider.currentText() == "llama_cpp"
        assert instance.setInformativeText.called

    def test_soft_wrap_path_inserts_break_opportunities(self):
        from src.gui.windows.settings_dialog import _soft_wrap_path

        assert _soft_wrap_path("C:\\a\\b.gguf") == "C:\\\u200ba\\\u200bb.gguf"
        assert _soft_wrap_path("h/x.gguf") == "h/\u200bx.gguf"


class _FakePackManager:
    def __init__(self, directory, pack_folder, manifest_name):
        from src.personality.personality_pack import PersonalityPackManager
        self._pm = PersonalityPackManager(str(directory))
        (directory / pack_folder).mkdir(exist_ok=True)
        (directory / pack_folder / "manifest.json").write_text(json.dumps({
            "name": manifest_name,
            "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")
        self._pm.scan_packs()

    def __getattr__(self, name):
        return getattr(self._pm, name)


class TestCharacterPackNameSync:
    def _config(self, tmp_path):
        return {
            "personality": {"name": "Tomo", "traits": "x"},
            "llm": {"model": "m", "endpoint": "http://localhost:1"},
            "modes": {},
            "personality_packs": {
                "enabled": True,
                "directory": str(tmp_path),
            },
            "context": {"directory": "data/context_packs"},
        }

    def test_save_with_active_pack_sets_name(self, qtbot, mock_i18n, tmp_path):
        from types import SimpleNamespace

        pm = _FakePackManager(tmp_path, "Lin", manifest_name="Lin")
        engine = SimpleNamespace(pack_manager=pm)
        cfg = self._config(tmp_path)
        dialog = _make_dialog(qtbot, cfg, mock_i18n, proactive_engine=engine)
        dialog.pack_enabled.setChecked(True)
        dialog.pack_active.setCurrentText("Lin")
        dialog._save_character()
        assert cfg["personality"]["name"] == "Lin"
        assert cfg["personality_packs"]["active_pack"] == "Lin"
        assert pm._active_pack == "Lin"
        assert dialog.pers_name.text() == "Lin"
        assert not dialog.pers_name.isEnabled()

    def test_save_disabled_pack_keeps_manual_name(self, qtbot, mock_i18n, tmp_path):
        from types import SimpleNamespace

        pm = _FakePackManager(tmp_path, "Lin", manifest_name="Lin")
        engine = SimpleNamespace(pack_manager=pm)
        cfg = self._config(tmp_path)
        dialog = _make_dialog(qtbot, cfg, mock_i18n, proactive_engine=engine)
        dialog.pack_enabled.setChecked(False)
        dialog.pers_name.setText("Zed")
        dialog._save_character()
        assert cfg["personality"]["name"] == "Zed"
        assert cfg["personality_packs"]["active_pack"] is None
        assert pm._active_pack is None
        assert dialog.pers_name.isEnabled()

    def test_folder_ref_resolves_to_manifest_key(self, qtbot, mock_i18n, tmp_path):
        from types import SimpleNamespace

        pm = _FakePackManager(tmp_path, "lin_folder", manifest_name="Lin")
        engine = SimpleNamespace(pack_manager=pm)
        cfg = self._config(tmp_path)
        dialog = _make_dialog(qtbot, cfg, mock_i18n, proactive_engine=engine)
        dialog.pack_enabled.setChecked(True)
        dialog.pack_active.setCurrentText("lin_folder")
        dialog._save_character()
        assert cfg["personality_packs"]["active_pack"] == "Lin"
        assert cfg["personality"]["name"] == "Lin"
        assert pm._active_pack == "Lin"

    def test_character_changed_emitted_once(self, qtbot, mock_i18n, tmp_path):
        from types import SimpleNamespace

        pm = _FakePackManager(tmp_path, "Lin", manifest_name="Lin")
        engine = SimpleNamespace(pack_manager=pm)
        cfg = self._config(tmp_path)
        dialog = _make_dialog(qtbot, cfg, mock_i18n, proactive_engine=engine)
        received = []
        dialog.character_changed.connect(received.append)
        dialog.pack_enabled.setChecked(True)
        dialog.pack_active.setCurrentText("Lin")
        dialog._save_character()
        dialog._save_character()
        assert received == ["Lin"]


class TestWindowSittingSettings:
    def test_target_options_and_legacy_migration(
        self, qtbot, mock_i18n, mock_config
    ):
        mock_config["window_sitting"] = {"target": "desktop"}
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        values = [
            dialog.ws_target.itemData(i) for i in range(dialog.ws_target.count())
        ]
        assert values == [
            "active_window", "mouse_window", "closest_window", "fixed_spot",
        ]
        assert dialog.ws_target.currentData() == "fixed_spot"

    def test_save_advanced_persists_selection(self, qtbot, mock_i18n, mock_config):
        mock_config["window_sitting"] = {}
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.ws_target.setCurrentIndex(dialog.ws_target.findData("mouse_window"))
        dialog.ws_fallback.setCurrentIndex(dialog.ws_fallback.findData("top-left"))
        dialog.ws_maximized.setCurrentIndex(dialog.ws_maximized.findData(0))
        dialog.ws_minimized.setCurrentIndex(dialog.ws_minimized.findData(1))
        dialog._save_advanced()
        ws = mock_config["window_sitting"]
        assert ws["target"] == "mouse_window"
        assert ws["fallback_position"] == "top-left"
        assert ws["maximized_behavior"] == 0
        assert ws["minimized_behavior"] == 1

    def test_save_advanced_pushes_to_overlay(self, qtbot, mock_i18n, mock_config):
        from types import SimpleNamespace

        mock_config["window_sitting"] = {}
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        overlay = MagicMock()
        dialog.parent = lambda: SimpleNamespace(overlay=overlay)
        dialog._save_advanced()
        overlay.apply_sitting_config.assert_called_once()
        pushed = overlay.apply_sitting_config.call_args[0][0]
        assert pushed["target"] == dialog.ws_target.currentData()

    def test_dnd_checkbox_not_inverted(self, qtbot, mock_i18n, mock_config):
        from types import SimpleNamespace

        policy = MagicMock()
        policy._focus_mode = False
        policy._dnd_mode = False
        mock_config["window_sitting"] = {}
        dialog = _make_dialog(
            qtbot, mock_config, mock_i18n,
            proactive_engine=SimpleNamespace(policy=policy),
        )
        dialog.behavior_dnd_cb.setChecked(True)
        dialog._save_behavior()
        policy.set_dnd_mode.assert_called_once_with(True)


def _platform_dependent_controls(dialog):
    return (
        dialog.ws_target,
        dialog.ws_fallback,
        dialog.ws_maximized,
        dialog.ws_minimized,
        dialog.privacy_monitor_cb,
    )


class TestPlatformCapabilitiesUI:
    def test_platform_group_is_first_on_advanced_page(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        texts = _group_texts(dialog._pages[5])
        assert len(texts) == 5
        assert texts[0] == "dialogs.settings.advanced_platform"
        assert texts[1] == "dialogs.settings.advanced_sitting"
        assert "dialogs.settings.advanced_database" in texts
        assert "dialogs.settings.advanced_logs" in texts
        assert "dialogs.settings.advanced_about" in texts

    def test_missing_capabilities_disable_controls_and_list_missing(
        self, qtbot, mock_config, mock_i18n, inject_platform
    ):
        inject_platform(
            window_enumeration=False,
            idle_time=False,
            taskbar_detection=False,
            taskbar_entry=False,
            open_path=False,
        )
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in _platform_dependent_controls(dialog):
            assert not control.isEnabled()
            assert control.toolTip() == "dialogs.settings.disabled_platform"
        assert (
            dialog.adv_platform_body.text()
            == "dialogs.settings.advanced_platform_body"
        )
        requested = [call.args[0] for call in mock_i18n.t.call_args_list]
        for key in (
            "dialogs.settings.cap_window_enumeration",
            "dialogs.settings.cap_idle_time",
            "dialogs.settings.cap_taskbar",
            "dialogs.settings.cap_open_path",
        ):
            assert key in requested

    def test_partial_missing_capabilities_only_list_missing(
        self, qtbot, mock_config, mock_i18n, inject_platform
    ):
        inject_platform(idle_time=False)
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in _platform_dependent_controls(dialog):
            assert control.isEnabled()
        assert (
            dialog.adv_platform_body.text()
            == "dialogs.settings.advanced_platform_body"
        )
        requested = [call.args[0] for call in mock_i18n.t.call_args_list]
        assert "dialogs.settings.cap_idle_time" in requested
        assert "dialogs.settings.cap_window_enumeration" not in requested
        assert "dialogs.settings.cap_taskbar" not in requested
        assert "dialogs.settings.cap_open_path" not in requested

    def test_full_capabilities_enable_controls(
        self, qtbot, mock_config, mock_i18n, inject_platform
    ):
        inject_platform()
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in _platform_dependent_controls(dialog):
            assert control.isEnabled()
            assert control.toolTip() == ""
        assert (
            dialog.adv_platform_body.text()
            == "dialogs.settings.advanced_platform_full"
        )
        requested = [call.args[0] for call in mock_i18n.t.call_args_list]
        assert "dialogs.settings.cap_window_enumeration" not in requested


class TestOpenLogsFolder:
    def test_uses_platform_adapter_open_path(
        self, qtbot, mock_config, mock_i18n, inject_platform, tmp_path
    ):
        adapter = inject_platform()
        adapter.open_path.return_value = False
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        with patch(
            "src.gui.windows.settings_dialog.log_dir", return_value=tmp_path
        ):
            dialog._on_open_logs_folder()  # must not raise
        adapter.open_path.assert_called_once_with(tmp_path)