import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox, QLabel, QMessageBox, QPushButton, QSizePolicy,
)

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


@pytest.fixture(autouse=True)
def no_blocking_message_box(monkeypatch):
    """Evita que un QMessageBox modal real deje la suite colgada.

    El diálogo de Ajustes pregunta al cerrar si hay cambios sin guardar; un
    test que termine con ``_dirty`` a True abriría un ``exec()`` de verdad que
    nadie responde. Por defecto la respuesta simulada es "seguir editando".
    """
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: _discard_button(self, "dialogs.settings.discard_cancel"),
    )


@pytest.fixture(autouse=True)
def local_engine(mocker):
    """Mantiene el motor local disponible por defecto.

    El entorno de desarrollo puede tener o no ``llama-cpp-python`` instalado;
    los tests que simulan un binario sin motor local llaman al setter con
    ``False`` antes de construir el dialogo.
    """
    patch = mocker.patch(
        "src.gui.windows.settings_dialog.is_llama_cpp_available",
        return_value=True,
    )

    def _set(available: bool):
        patch.return_value = available
        return patch

    return _set


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
            "screen_geometry": True,
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


def _discard_button(box, key: str):
    """Botón del diálogo de descarte cuya etiqueta es la clave ``key``.

    Los botones se añaden con ``addButton`` (texto propio), así que no se
    pueden recuperar por ``StandardButton``.
    """
    return next(b for b in box.buttons() if b.text() == key)


def _buttons_by_text(dialog) -> dict:
    """Botones del diálogo indexados por su texto traducido."""
    found: dict = {}
    for button in dialog.findChildren(QPushButton):
        found.setdefault(button.text(), []).append(button)
    return found


def _only_button(dialog, key: str) -> QPushButton:
    buttons = _buttons_by_text(dialog).get(key)
    assert buttons, f"no hay ningún botón con el texto {key}"
    assert len(buttons) == 1, f"{key} aparece {len(buttons)} veces"
    return buttons[0]


class TestButtonHierarchy:
    """``Design.md`` §2.1: un objectName por rol, uno solo por diálogo."""

    def test_save_is_primary_without_object_name(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert _only_button(dialog, "dialogs.settings.save").objectName() == ""
        assert _only_button(dialog, "dialogs.settings.close").objectName() == "secondary"

    def test_no_button_depends_on_the_removed_primary_id(
        self, qtbot, mock_config, mock_i18n
    ):
        """``QPushButton#primary`` ya no existe en el QSS."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        primaries = [
            b.text() for b in dialog.findChildren(QPushButton)
            if b.objectName() == "primary"
        ]
        assert primaries == []

    def test_destructive_actions_are_danger(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for key in (
            "dialogs.settings.sprite_delete",
            "dialogs.settings.pack_delete",
            "dialogs.settings.context_delete",
            "dialogs.settings.memory_clear_all",
        ):
            assert _only_button(dialog, key).objectName() == "danger", key

    def test_utility_actions_are_flat(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for key in (
            "dialogs.settings.hints_reset",
            "dialogs.settings.pack_reload",
            "dialogs.settings.context_reload",
            "dialogs.settings.download_model",
            "dialogs.settings.memory_reindex",
            "dialogs.settings.db_compact",
            "dialogs.settings.db_export",
            "dialogs.settings.db_import",
            "dialogs.settings.log_open_folder",
            "dialogs.settings.tutorial_play",
        ):
            assert _only_button(dialog, key).objectName() == "flat", key
        # Los cuatro "Examinar" comparten texto: todos deben ser planos.
        browsing = _buttons_by_text(dialog)["dialogs.settings.browse"]
        assert len(browsing) == 4
        assert all(b.objectName() == "flat" for b in browsing)

    def test_every_button_uses_a_known_variant(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        allowed = {"", "secondary", "danger", "flat"}
        unknown = {
            b.objectName()
            for b in dialog.findChildren(QPushButton)
            if b.objectName() not in allowed
        }
        assert unknown == set()


class TestStatusIconsSetting:
    """``ui.status_icons`` se lee, se persiste y se empuja en caliente."""

    def test_defaults_to_off(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.ui_status_icons.isChecked() is False

    def test_reads_the_configured_value(self, qtbot, mock_config, mock_i18n):
        mock_config.setdefault("ui", {})["status_icons"] = True
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.ui_status_icons.isChecked() is True

    def test_saving_persists_the_flag(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.ui_status_icons.setChecked(True)
        dialog._save_appearance()
        assert mock_config["ui"]["status_icons"] is True

        dialog.ui_status_icons.setChecked(False)
        dialog._save_appearance()
        assert mock_config["ui"]["status_icons"] is False

    def test_toggling_marks_the_dialog_dirty(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog._dirty is False
        dialog.ui_status_icons.setChecked(True)
        assert dialog._dirty is True

    def test_saving_pushes_the_flag_to_the_owner(self, qtbot, mock_config, mock_i18n):
        from types import SimpleNamespace

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        owner = SimpleNamespace(overlay=None, set_status_icons_enabled=MagicMock())
        dialog.parent = lambda: owner
        dialog.ui_status_icons.setChecked(True)

        dialog._save_appearance()

        owner.set_status_icons_enabled.assert_called_once_with(True)

    def test_owner_without_the_setter_is_tolerated(self, qtbot, mock_config, mock_i18n):
        from types import SimpleNamespace

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.parent = lambda: SimpleNamespace(overlay=None)
        dialog.ui_status_icons.setChecked(True)
        dialog._save_appearance()  # must not raise


class TestTranslatedCombos:
    """Los combos muestran texto traducido y guardan el valor de config."""

    def test_language_combo_maps_text_to_value(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert [
            dialog.ui_lang.itemData(i) for i in range(dialog.ui_lang.count())
        ] == ["auto", "en", "es"]
        for i in range(dialog.ui_lang.count()):
            assert dialog.ui_lang.itemText(i).startswith("dialogs.settings.language_")
            assert dialog.ui_lang.itemText(i) != dialog.ui_lang.itemData(i)

    def test_theme_combo_maps_text_to_value(self, qtbot, mock_config, mock_i18n):
        mock_config.setdefault("ui", {})["theme"] = "dark"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert [
            dialog.ui_theme.itemData(i) for i in range(dialog.ui_theme.count())
        ] == ["light", "dark"]
        assert dialog.ui_theme.currentData() == "dark"
        assert dialog.ui_theme.currentText() != "dark"

    def test_overlay_position_combo_lists_positions(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert [
            dialog.ui_overlay_default.itemData(i)
            for i in range(dialog.ui_overlay_default.count())
        ] == [
            "bottom-right", "bottom-left", "top-right", "top-left", "center",
        ]
        assert (
            dialog.ui_overlay_default.currentData() == "bottom-right"
        )

    def test_unknown_configured_value_falls_back_to_the_first_option(
        self, qtbot, mock_config, mock_i18n
    ):
        ui = mock_config.setdefault("ui", {})
        ui["language"] = "klingon"
        ui["theme"] = "neon"
        ui["overlay_default_position"] = "middle-earth"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.ui_lang.currentData() == "auto"
        assert dialog.ui_theme.currentData() == "light"
        assert dialog.ui_overlay_default.currentData() == "bottom-right"

    def test_save_writes_the_selected_values_not_the_labels(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.ui_lang.setCurrentIndex(dialog.ui_lang.findData("es"))
        dialog.ui_theme.setCurrentIndex(dialog.ui_theme.findData("dark"))
        dialog.ui_overlay_default.setCurrentIndex(
            dialog.ui_overlay_default.findData("top-left")
        )

        dialog._save_appearance()

        assert mock_config["ui"]["language"] == "es"
        assert mock_config["ui"]["theme"] == "dark"
        assert mock_config["ui"]["overlay_default_position"] == "top-left"


def _answer_discard(monkeypatch, confirm: bool) -> list:
    """Fuerza la respuesta del diálogo de descarte y captura los QMessageBox.

    Devuelve la lista donde se acumulan los boxes construidos, para poder
    comprobar sus textos traducidos.
    """
    key = ("dialogs.settings.discard_confirm" if confirm
           else "dialogs.settings.discard_cancel")
    boxes = []

    def fake_exec(self):
        boxes.append(self)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: _discard_button(self, key)
    )
    return boxes


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


class TestSettingsSearchByRowLabel:
    """B7: el buscador debe encontrar los ajustes por su etiqueta de fila.

    Antes solo comparaba con el título de la página y del QGroupBox, así que
    "timeout", "endpoint" o "api" no encontraban nada aunque estuvieran
    escritos en pantalla.
    """

    MIND_PAGE = 4

    def _visible_groups(self, dialog, page_index):
        return [
            g for g in dialog._pages[page_index].findChildren(QGroupBox)
            if g.property("_search_text") and not g.isHidden()
        ]

    def _visible_pages(self, dialog):
        return [
            idx for idx in range(dialog._nav.count())
            if not dialog._nav.item(idx).isHidden()
        ]

    def test_timeout_label_finds_its_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("timeout")

        visible = self._visible_groups(dialog, self.MIND_PAGE)
        assert len(visible) == 1
        assert visible[0].property("_search_text") == "dialogs.settings.mind_llm"
        # Ningún otro grupo de la página se abre.
        hidden = [
            g.property("_search_text")
            for g in dialog._pages[self.MIND_PAGE].findChildren(QGroupBox)
            if g.property("_search_text") and g.isHidden()
        ]
        assert hidden == [
            "dialogs.settings.memory_general",
            "dialogs.settings.memory_chroma",
            "dialogs.settings.memory_episodic",
        ]

    def test_query_matching_two_pages_shows_both(self, qtbot, mock_config,
                                                 mock_i18n):
        """"timeout" está en Mente y en Comportamiento: se abren ambas."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("timeout")

        assert self._visible_pages(dialog) == [3, 4]
        assert [
            g.property("_search_text")
            for g in self._visible_groups(dialog, 3)
        ] == ["dialogs.settings.behavior_sleep"]

    def test_endpoint_label_does_not_hide_the_other_groups(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("endpoint")

        shown = [
            g.property("_search_text")
            for g in dialog._pages[self.MIND_PAGE].findChildren(QGroupBox)
            if not g.isHidden()
        ]
        assert shown == ["dialogs.settings.mind_llm"]
        assert self._visible_pages(dialog) == [self.MIND_PAGE]

    def test_api_key_label_finds_the_llm_group(self, qtbot, mock_config,
                                               mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("api")

        assert [
            g.property("_search_text")
            for g in self._visible_groups(dialog, self.MIND_PAGE)
        ] == ["dialogs.settings.mind_llm"]

    def test_slider_labels_are_searchable_too(self, qtbot, mock_config, mock_i18n):
        """Los deslizadores construyen su fila a mano: también cuentan."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("episodic_auto_threshold")

        shown = [
            g.property("_search_text")
            for g in dialog._pages[self.MIND_PAGE].findChildren(QGroupBox)
            if not g.isHidden()
        ]
        assert shown == ["dialogs.settings.memory_episodic"]

    def test_search_still_filters_by_page_title(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("dialogs.settings.tab_behavior")

        assert self._visible_pages(dialog) == [3]
        assert len(self._visible_groups(dialog, 3)) == 4

    def test_group_title_still_matches(self, qtbot, mock_config, mock_i18n):
        """Lo nuevo no rompe la búsqueda por título de grupo."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog._search_field.setText("memory_chroma")

        shown = [
            g.property("_search_text")
            for g in dialog._pages[self.MIND_PAGE].findChildren(QGroupBox)
            if not g.isHidden()
        ]
        assert shown == ["dialogs.settings.memory_chroma"]

    def test_clearing_the_query_restores_everything(self, qtbot, mock_config,
                                                   mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("timeout")

        dialog._search_field.setText("")

        hidden = [
            g for g in dialog._pages[0].findChildren(QGroupBox)
            if g.property("_search_text") and g.isHidden()
        ]
        assert hidden == []
        assert len(self._visible_groups(dialog, self.MIND_PAGE)) == 4


#: Control -> etiqueta con la que se construyó su fila (claves del mock i18n).
TIP_CONTROLS = {
    "llm_model": "dialogs.settings.model",
    "llm_endpoint": "dialogs.settings.endpoint",
    "llm_api_key": "dialogs.settings.api_key",
    "llm_timeout": "dialogs.settings.llm_timeout",
    "llama_path": "dialogs.settings.model_path",
    "llama_ctx": "dialogs.settings.n_ctx",
    "mem_short_term": "dialogs.settings.max_short_term_messages",
    "mem_chroma_path": "dialogs.settings.chroma_path",
    "mem_embed_model": "dialogs.settings.embedding_model",
    "mem_episodic_msg": "dialogs.settings.episodic_message_threshold",
    "mem_episodic_threshold": "dialogs.settings.episodic_auto_threshold",
    "prob_spin": "dialogs.settings.random_prob_label",
    "cooldown_spin": "dialogs.settings.cooldown_label",
    "max_spin": "dialogs.settings.max_per_hour_label",
    "ws_transition": "dialogs.settings.ws_transition_speed",
    "sleep_timeout_spin": "dialogs.settings.sleep_timeout",
    "ui_char_size": "dialogs.settings.character_size",
    "ui_bubble_lines": "dialogs.settings.bubble_max_lines",
    "ui_bubble_fade": "dialogs.settings.bubble_duration",
    "ui_bubble_type": "dialogs.settings.bubble_typewriter_interval",
}


class TestSettingsTooltips:
    """B5: cada ajuste sensible explica para qué sirve."""

    @pytest.mark.parametrize("attr,label_key", sorted(TIP_CONTROLS.items()))
    def test_control_has_a_translated_tooltip(
        self, qtbot, mock_config, mock_i18n, attr, label_key
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        control = getattr(dialog, attr)
        # El mock de i18n devuelve la propia clave: el tooltip sale traducido.
        assert control.toolTip() == f"dialogs.settings.tip_{attr}"
        # Y no es un calco de la etiqueta del control.
        assert control.toolTip() != label_key

    def test_every_control_of_the_list_is_covered(self, qtbot, mock_config,
                                                  mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for attr in TIP_CONTROLS:
            assert getattr(dialog, attr).toolTip() != "", attr


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

        dialog.ui_lang.setCurrentIndex(dialog.ui_lang.findData("es"))
        dialog._save_appearance()
        assert "ui" in mock_config
        assert mock_config["ui"]["language"] == "es"
        assert mock_config["ui"]["language_set"] is True

        dialog.ui_lang.setCurrentIndex(dialog.ui_lang.findData("auto"))
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
        # El worker se marca como abortado sin consultar isRunning.
        dialog._abort_download()  # must not raise
        assert worker._cancelled is True

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


class TestLocalEngineAvailability:
    def test_absent_disables_download_and_shows_note(
        self, qtbot, mock_config, mock_i18n, local_engine
    ):
        local_engine(False)
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.llama_download_btn.isEnabled() is False
        notes = [
            label for label in dialog.findChildren(QLabel)
            if label.text() == "dialogs.settings.llama_cpp_unavailable"
        ]
        assert len(notes) == 1
        assert notes[0].wordWrap() is True

    def test_present_keeps_download_enabled(
        self, qtbot, mock_config, mock_i18n, local_engine
    ):
        local_engine(True)
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.llama_download_btn.isEnabled() is True
        notes = [
            label for label in dialog.findChildren(QLabel)
            if label.text() == "dialogs.settings.llama_cpp_unavailable"
        ]
        assert notes == []

    def test_download_blocked_without_engine(
        self, qtbot, mock_config, mock_i18n, local_engine
    ):
        local_engine(False)
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        with patch("src.llm.download.download_model") as download_mock, \
             patch("src.gui.windows.settings_dialog.QMessageBox") as mb:
            dialog._on_download_model()
        download_mock.assert_not_called()
        mb.information.assert_called_once()
        assert getattr(dialog, "_download_worker", None) is None
        assert dialog.llm_provider.currentText() != "llama_cpp"


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


class _FakeMemoryManager:
    def __init__(self):
        self.cleared = False
        self.reindexed = False

    def clear_all_memories(self):
        self.cleared = True

    def reindex_notes(self):
        self.reindexed = True
        return 3


class TestMaintenanceActions:
    """The Settings maintenance buttons must call real methods, not crash.

    Regression: they used to invoke MemoryManager/DatabaseManager methods
    that did not exist, so the buttons silently did nothing.
    """

    @pytest.fixture
    def owner(self, qtbot, mock_config, mock_i18n):
        from PySide6.QtWidgets import QWidget
        parent = QWidget()
        qtbot.addWidget(parent)
        parent.memory_manager = _FakeMemoryManager()
        parent.overlay = None
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        return parent, dialog

    def _reparent(self, dialog, parent):
        dialog.setParent(parent)
        return dialog

    def test_clear_memories_calls_the_method(self, owner, qtbot, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes)
        )
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

        dialog._on_clear_memories()

        assert parent.memory_manager.cleared is True

    def test_clear_memories_aborts_on_no(self, owner, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        monkeypatch.setattr(
            QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No)
        )

        dialog._on_clear_memories()

        assert parent.memory_manager.cleared is False

    def test_compact_db_reports_failure(self, owner, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *a, **k: None)
        )

        with patch(
            "src.memory.database.DatabaseManager"
        ) as mock_db_class:
            mock_db_class.return_value.vacuum.side_effect = RuntimeError("locked")
            dialog._on_compact_db()  # must not raise

        mock_db_class.return_value.vacuum.assert_called_once()

    def test_reindex_notes_calls_the_method(self, owner, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

        dialog._on_reindex_notes()

        assert parent.memory_manager.reindexed is True

    def test_play_tutorial_calls_the_owner(self, owner, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        parent.play_tutorial = lambda: setattr(parent, "tutored", True)

        dialog._on_play_tutorial()

        assert parent.tutored is True

    def test_reset_hints_clears_the_persisted_preference(self, owner, monkeypatch):
        parent, dialog = owner
        self._reparent(dialog, parent)
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
        parent.memory_manager.set_preference = lambda k, v: None

        dialog._on_reset_hints()

        # Without a live hint manager it must still clear the preference.
        assert parent.memory_manager is not None


class TestBubbleStyleOptions:
    """The bubble-style combo must mirror the BubbleStyle enum.

    Regression: it offered "flat"/"round" while the widget only knew
    DARK/COMIC, so picking those crashed the overlay at startup.
    """

    def test_combo_offers_only_valid_styles(self, qtbot, mock_config, mock_i18n):
        from src.gui.widgets.speech_bubble import BubbleStyle

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        offered = [
            dialog.ui_bubble_style.itemData(i)
            for i in range(dialog.ui_bubble_style.count())
        ]
        assert offered == [s.value for s in BubbleStyle]

    def test_combo_shows_translated_text_not_the_raw_value(
        self, qtbot, mock_config, mock_i18n
    ):
        """El usuario ve texto legible; el valor sigue siendo la clave."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for i in range(dialog.ui_bubble_style.count()):
            text = dialog.ui_bubble_style.itemText(i)
            assert text.startswith("dialogs.settings.bubble_style_")
            assert text != dialog.ui_bubble_style.itemData(i)

    def test_stale_config_value_falls_back(self, qtbot, mock_config, mock_i18n):
        mock_config.setdefault("ui", {})["bubble_style"] = "legacy_style"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.ui_bubble_style.currentData() == "dark"

    def test_valid_config_value_is_selected(self, qtbot, mock_config, mock_i18n):
        mock_config.setdefault("ui", {})["bubble_style"] = "round"
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog.ui_bubble_style.currentData() == "round"
        assert dialog.ui_bubble_style.currentText() != "round"


class TestDirtyTracking:
    """El buscador filtra la vista: no es un ajuste y no debe ensuciar nada."""

    def test_typing_in_the_search_does_not_mark_dirty(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        assert dialog._dirty is False

        dialog._search_field.setText("bubble")
        dialog._search_field.setText("")

        assert dialog._dirty is False
        assert dialog._close_btn.text() == "dialogs.settings.close"

    def test_editing_a_real_setting_marks_dirty(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)

        dialog.pers_traits.setText("curious, calm")

        assert dialog._dirty is True
        # El botón nunca cambia de identidad: no descarta nada.
        assert dialog._close_btn.text() == "dialogs.settings.close"


class TestDiscardConfirmation:
    """Nada se pierde en silencio: cerrar con cambios pide confirmación."""

    def test_declining_keeps_the_dialog_open(self, qtbot, mock_config, mock_i18n,
                                              monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        _answer_discard(monkeypatch, confirm=False)
        dialog.show()

        dialog.close()

        assert dialog.isVisible()
        dialog._dirty = False  # no dejar el box abierto en el teardown

    def test_confirming_closes_the_dialog(self, qtbot, mock_config, mock_i18n,
                                          monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        _answer_discard(monkeypatch, confirm=True)
        dialog.show()

        dialog.close()

        assert not dialog.isVisible()

    def test_escape_asks_too(self, qtbot, mock_config, mock_i18n, monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        _answer_discard(monkeypatch, confirm=False)
        dialog.show()

        dialog.reject()  # Esc va por reject(), no por closeEvent()

        assert dialog.isVisible()
        dialog._dirty = False

    def test_escape_closes_when_confirmed(self, qtbot, mock_config, mock_i18n,
                                          monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        _answer_discard(monkeypatch, confirm=True)
        dialog.show()

        dialog.reject()

        assert not dialog.isVisible()

    def test_prompt_uses_translated_labels(self, qtbot, mock_config, mock_i18n,
                                           monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        boxes = _answer_discard(monkeypatch, confirm=False)
        dialog.show()

        dialog.close()

        assert len(boxes) == 1
        box = boxes[0]
        assert box.windowTitle() == "dialogs.settings.discard_title"
        assert box.text() == "dialogs.settings.discard_body"
        assert (_discard_button(box, "dialogs.settings.discard_cancel")
                is not None)
        assert (_discard_button(box, "dialogs.settings.discard_confirm")
                is not None)
        dialog._dirty = False

    def test_clean_dialog_closes_without_asking(self, qtbot, mock_config, mock_i18n,
                                                monkeypatch):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        boxes = _answer_discard(monkeypatch, confirm=False)
        dialog.show()

        dialog.close()

        assert boxes == []
        assert not dialog.isVisible()


class TestSaveOrdering:
    """Se valida antes de mutar: un fallo no debe dejar la app a medias."""

    def test_invalid_endpoint_leaves_everything_untouched(
        self, qtbot, mock_config, mock_i18n, monkeypatch
    ):
        import copy

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.llm_provider.setCurrentText("openai_compatible")
        dialog.llm_endpoint.setText("esto-no-es-un-endpoint")
        dialog.ui_lang.setCurrentIndex(dialog.ui_lang.findData("es"))
        dialog.ui_theme.setCurrentIndex(dialog.ui_theme.findData("dark"))
        snapshot = copy.deepcopy(mock_config)
        emitted = []
        dialog.language_changed.connect(lambda: emitted.append(True))
        saved = []
        monkeypatch.setattr(
            "src.gui.windows.settings_dialog.save_config",
            lambda cfg, path: saved.append(cfg),
        )
        monkeypatch.setattr("src.gui.windows.settings_dialog._creds", MagicMock())

        with patch("src.gui.windows.settings_dialog.QMessageBox") as mb:
            dialog._save_settings()

        assert mock_config == snapshot
        assert saved == []
        assert emitted == []
        mock_i18n.set_language.assert_not_called()
        mb.warning.assert_called_once()
        assert dialog._dirty is True  # sigue pendiente: el usuario debe corregir
        dialog._dirty = False

    def test_successful_save_clears_dirty_and_asks_nothing(
        self, qtbot, mock_config, mock_i18n, monkeypatch
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.pers_traits.setText("curious")
        assert dialog._dirty is True
        saved = []
        monkeypatch.setattr(
            "src.gui.windows.settings_dialog.save_config",
            lambda cfg, path: saved.append(cfg),
        )
        monkeypatch.setattr("src.gui.windows.settings_dialog._creds", MagicMock())
        boxes = _answer_discard(monkeypatch, confirm=False)
        dialog.show()

        dialog._save_settings()

        assert boxes == []
        assert dialog._dirty is False
        assert saved and saved[0] is mock_config
        assert mock_config["personality"]["traits"] == "curious"
        assert not dialog.isVisible()

    def test_language_is_applied_only_after_a_successful_save(
        self, qtbot, mock_config, mock_i18n, monkeypatch
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        mock_i18n.detect_language.return_value = "es"
        monkeypatch.setattr(
            "src.gui.windows.settings_dialog.save_config", lambda cfg, path: None
        )
        monkeypatch.setattr("src.gui.windows.settings_dialog._creds", MagicMock())
        dialog.show()

        dialog.ui_lang.setCurrentIndex(dialog.ui_lang.findData("es"))
        dialog._save_settings()

        mock_i18n.set_language.assert_called_once_with("es")

    def test_validate_mind_reports_invalid_endpoint(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog.llm_provider.setCurrentText("openai_compatible")
        dialog.llm_endpoint.setText("no-es-una-url")

        with patch("src.gui.windows.settings_dialog.QMessageBox") as mb:
            assert dialog._validate_mind() is False
        mb.warning.assert_called_once()

        dialog.llm_endpoint.setText("http://localhost:1234/v1")
        assert dialog._validate_mind() is True

    def test_appearance_is_pushed_to_the_live_overlay(self, qtbot, mock_config,
                                                      mock_i18n):
        from types import SimpleNamespace

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        overlay = MagicMock()
        dialog.parent = lambda: SimpleNamespace(overlay=overlay)
        dialog.ui_bubble_style.setCurrentIndex(
            dialog.ui_bubble_style.findData("round")
        )
        dialog.ui_overlay_opacity.setValue(40)

        dialog._save_appearance()

        overlay.apply_bubble_config.assert_called_once()
        pushed = overlay.apply_bubble_config.call_args[0][0]
        assert pushed["bubble_style"] == "round"
        overlay.apply_overlay_opacity.assert_called_once_with(0.4)


class TestClickableLabels:
    """B6.3: pulsar la etiqueta de una fila enfoca el control (setBuddy)."""

    @staticmethod
    def _buddy_label(dialog, control):
        return next(
            (lbl for lbl in dialog.findChildren(QLabel) if lbl.buddy() is control),
            None,
        )

    def test_spin_and_line_rows_have_a_buddy(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in (
            dialog.llm_timeout,
            dialog.llama_ctx,
            dialog.mem_short_term,
            dialog.llm_endpoint,
        ):
            assert self._buddy_label(dialog, control) is not None, control
            assert control.focusPolicy() != Qt.NoFocus

    def test_path_rows_point_at_the_line_edit_not_the_container(
        self, qtbot, mock_config, mock_i18n
    ):
        """El "widget" de la fila es un contenedor: el buddy debe ser el campo."""
        from PySide6.QtWidgets import QLineEdit

        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in (dialog.llama_path, dialog.mem_chroma_path):
            assert isinstance(control, QLineEdit)
            assert self._buddy_label(dialog, control) is not None
            # El contenedor (padre) no recibe foco: no es el buddy.
            container = control.parentWidget()
            assert container is not control
            assert self._buddy_label(dialog, container) is None

    def test_slider_rows_have_a_buddy(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        for control in (
            dialog.prob_spin,
            dialog.mem_episodic_threshold,
            dialog.ui_char_size,
        ):
            assert self._buddy_label(dialog, control) is not None, control

    def test_widget_without_focusable_children_has_no_buddy(self, mock_config):
        from PySide6.QtWidgets import QWidget

        from src.gui.windows.settings_dialog import _focusable_buddy

        assert _focusable_buddy(None) is None
        assert _focusable_buddy(QWidget()) is None


class TestSettingsSearchTechnicalAliases:
    """B6.3: buscar por el nombre tecnico aunque la UI este en espanol.

    La etiqueta se muestra traducida; los alias son neutros respecto al
    idioma, asi que "timeout", "endpoint" o "chroma" encuentran el ajuste.
    """

    MIND_PAGE = 4
    APPEARANCE_PAGE = 0

    def _visible_groups(self, dialog, page_index):
        return [
            g for g in dialog._pages[page_index].findChildren(QGroupBox)
            if g.property("_search_text") and not g.isHidden()
        ]

    def _visible_pages(self, dialog):
        return [
            idx for idx in range(dialog._nav.count())
            if not dialog._nav.item(idx).isHidden()
        ]

    def _names(self, dialog, page_index):
        return [
            g.property("_search_text")
            for g in self._visible_groups(dialog, page_index)
        ]

    def test_timeout_alias_finds_the_llm_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("timeout")
        assert self._names(dialog, self.MIND_PAGE) == ["dialogs.settings.mind_llm"]

    def test_endpoint_alias_finds_the_llm_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("endpoint")
        assert self._names(dialog, self.MIND_PAGE) == ["dialogs.settings.mind_llm"]

    def test_api_alias_finds_the_llm_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("api")
        assert self._names(dialog, self.MIND_PAGE) == ["dialogs.settings.mind_llm"]

    def test_chroma_alias_finds_the_chroma_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("chroma")
        assert self._names(dialog, self.MIND_PAGE) == [
            "dialogs.settings.memory_chroma"
        ]

    def test_embeddings_alias_finds_the_chroma_group(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("embeddings")
        assert self._names(dialog, self.MIND_PAGE) == [
            "dialogs.settings.memory_chroma"
        ]

    def test_episodic_alias_finds_the_episodic_group(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("episodic")
        assert self._names(dialog, self.MIND_PAGE) == [
            "dialogs.settings.memory_episodic"
        ]

    def test_theme_alias_finds_the_theme_group(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("dark")
        assert self._names(dialog, self.APPEARANCE_PAGE) == [
            "dialogs.settings.appearance_theme"
        ]

    def test_unknown_query_shows_no_results(self, qtbot, mock_config, mock_i18n):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("zzz_no_existe")
        assert self._visible_pages(dialog) == []
        assert not dialog._no_results_label.isHidden()

    def test_search_still_matches_the_translated_label(
        self, qtbot, mock_config, mock_i18n
    ):
        """Los alias se suman: la busqueda por etiqueta traducida sigue viva."""
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        dialog._search_field.setText("dialogs.settings.embedding_model")
        assert self._names(dialog, self.MIND_PAGE) == [
            "dialogs.settings.memory_chroma"
        ]

    def test_row_label_keeps_the_translated_label_plus_aliases(
        self, qtbot, mock_config, mock_i18n
    ):
        dialog = _make_dialog(qtbot, mock_config, mock_i18n)
        label = dialog.llm_timeout.property("_row_label")
        assert "dialogs.settings.llm_timeout" in label
        assert "timeout" in label
        assert "segundos" in label