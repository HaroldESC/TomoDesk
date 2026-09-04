import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QMessageBox

from src.context.context_pack import ContextPackManager


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