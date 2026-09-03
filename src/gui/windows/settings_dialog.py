import ctypes
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QProgressDialog, QPushButton, QScrollArea, QSlider,
    QSpinBox, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
    QListWidgetItem,
)

from src.config.config import get_config_path, save_config, validate_llm_endpoint
from src.config.credentials import CredentialManager
from src.config.paths import (
    bundled_defaults_dir,
    default_sprite_dir,
    is_frozen,
    log_dir,
    resolve as resolve_path,
    user_resolve,
)
from src.context.context_pack import ContextPackManager
from src.gui.sprites.sprite_loader import SpriteLoader
from src.gui.styles.styles import get_style_set


if sys.platform == "win32":
    _WS_EX_APPWINDOW = 0x00040000
    _GWL_EXSTYLE = -20


def _force_taskbar_entry(widget):
    if sys.platform != "win32":
        return
    widget.winId()
    hwnd = int(widget.winId())
    current = ctypes.windll.user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, current | _WS_EX_APPWINDOW)

logger = logging.getLogger(__name__)
_creds = CredentialManager()


class _ModelDownloadWorker(QThread):
    """Descarga el GGUF en segundo plano sin bloquear el hilo de UI."""

    progress = Signal(int, int)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._cancelled = False

    def request_cancel(self):
        self._cancelled = True

    def run(self):
        from src.llm import download as dl

        def _progress(done, total):
            if self._cancelled:
                raise _DownloadCancelled()
            self.progress.emit(done, total)

        try:
            dest = dl.download_model(self._config, progress=_progress)
            self.done.emit(dest)
        except _DownloadCancelled:
            self.error.emit("cancelled")
        except Exception as exc:
            self.error.emit(str(exc))


class _DownloadCancelled(Exception):
    """Señal interna para abortar una descarga en curso."""


class SettingsDialog(QDialog):
    sprite_changed = Signal(str)
    language_changed = Signal()

    def __init__(self, config, proactive_engine=None, parent=None, i18n=None, styles=None,
                 context_manager=None):
        super().__init__(parent)
        self.config = config
        self.proactive_engine = proactive_engine
        self.i18n = i18n
        if styles is None:
            styles = get_style_set("light")
        self.setWindowTitle(self.i18n.t("dialogs.settings.title"))
        self.setMinimumSize(760, 580)
        self.setStyleSheet(styles["dialog"])
        self._sprite_loader = SpriteLoader(config, str(default_sprite_dir()))
        ctx_bundled = bundled_defaults_dir("data", "context_packs")
        self.context_manager = context_manager or ContextPackManager(
            config,
            str(resolve_path(config, "context", "directory")),
            bundled_dir=str(ctx_bundled) if ctx_bundled else None,
        )
        self._dirty = False
        self._setup_ui()
        self._connect_dirty_tracking()
        _force_taskbar_entry(self)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _add_row(self, layout, label, widget):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(130)
        row.addWidget(lbl, 0)
        row.addWidget(widget, 1)
        layout.addLayout(row)

    def _add_group(self, layout, title_key, controls_builder):
        group = QGroupBox(self.i18n.t(title_key))
        group.setProperty("_search_text", self.i18n.t(title_key).lower())
        gl = QVBoxLayout(group)
        gl.setContentsMargins(12, 8, 12, 8)
        controls_builder(gl)
        layout.addWidget(group)

    def _make_page(self, nav_key):
        page = QWidget()
        page.setProperty("_search_text", self.i18n.t(nav_key).lower())
        page_layout = QVBoxLayout(page)
        heading = QLabel(self.i18n.t(nav_key))
        heading.setObjectName("page_heading")
        page_layout.addWidget(heading)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        page_layout.addWidget(self._scrollable(body), 1)
        return page, body_layout

    def _slider_with_label(self, lo, hi, val, suffix="%"):
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        lbl = QLabel(f"{val}{suffix}")
        s.valueChanged.connect(lambda v, l=lbl, sf=suffix: l.setText(f"{v}{sf}"))
        row = QHBoxLayout()
        row.addWidget(s, stretch=1)
        row.addWidget(lbl)
        return s, row

    def _labeled_slider(self, layout, label, lo, hi, val, suffix="%"):
        s, row = self._slider_with_label(lo, hi, val, suffix)
        row.insertWidget(0, QLabel(label))
        layout.addLayout(row)
        return s

    def _scrollable(self, widget, hmargin=75):
        widget.setContentsMargins(hmargin, 0, hmargin, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(widget)
        return scroll

    # ── 1. Apariencia ────────────────────────────────────────────────────────

    def _build_appearance_page(self, layout):
        self._add_group(layout, "dialogs.settings.appearance_theme", self._build_appearance_theme)
        self._add_group(layout, "dialogs.settings.appearance_bubble", self._build_appearance_bubble)
        self._add_group(layout, "dialogs.settings.appearance_hints", self._build_appearance_hints)
        layout.addStretch()

    def _build_appearance_theme(self, layout):
        ui = self.config.get("ui", {})

        self.ui_lang = QComboBox()
        self.ui_lang.addItems(["auto", "en", "es"])
        self.ui_lang.setCurrentText(ui.get("language", "auto"))
        self._add_row(layout, self.i18n.t("dialogs.settings.language"), self.ui_lang)

        self.ui_theme = QComboBox()
        self.ui_theme.addItems(["light", "dark"])
        self.ui_theme.setCurrentText(ui.get("theme", "light"))
        self._add_row(layout, self.i18n.t("dialogs.settings.theme"), self.ui_theme)

        self.ui_char_size = self._labeled_slider(
            layout, self.i18n.t("dialogs.settings.character_size"),
            50, 500, ui.get("character_size", 150), "px",
        )

        self.ui_overlay_default = QComboBox()
        self.ui_overlay_default.addItems([
            "bottom-right", "bottom-left", "top-right", "top-left", "center",
        ])
        self.ui_overlay_default.setCurrentText(
            ui.get("overlay_default_position", "bottom-right"),
        )
        self._add_row(layout, self.i18n.t("dialogs.settings.overlay_default_position"),
                      self.ui_overlay_default)

        self.ui_overlay_opacity = self._labeled_slider(
            layout, self.i18n.t("dialogs.settings.overlay_opacity"),
            0, 100, int(ui.get("overlay_opacity", 1.0) * 100),
        )

    def _build_appearance_bubble(self, layout):
        ui = self.config.get("ui", {})

        self.ui_overlay = QCheckBox(self.i18n.t("dialogs.settings.overlay_enabled"))
        self.ui_overlay.setChecked(ui.get("overlay_enabled", True))
        layout.addWidget(self.ui_overlay)

        self.ui_bubble_style = QComboBox()
        self.ui_bubble_style.addItems(["comic", "flat", "round"])
        self.ui_bubble_style.setCurrentText(ui.get("bubble_style", "comic"))
        self._add_row(layout, self.i18n.t("dialogs.settings.bubble_style"), self.ui_bubble_style)

        self.ui_bubble_lines = QSpinBox()
        self.ui_bubble_lines.setRange(1, 20)
        self.ui_bubble_lines.setValue(ui.get("bubble_max_lines", 5))
        self._add_row(layout, self.i18n.t("dialogs.settings.bubble_max_lines"), self.ui_bubble_lines)

        self.ui_bubble_type = QSpinBox()
        self.ui_bubble_type.setRange(0, 500)
        self.ui_bubble_type.setSuffix(" ms")
        self.ui_bubble_type.setValue(ui.get("bubble_typewriter_interval_ms", 30))
        self._add_row(layout, self.i18n.t("dialogs.settings.bubble_typewriter_interval"),
                      self.ui_bubble_type)

        self.ui_bubble_fade = QSpinBox()
        self.ui_bubble_fade.setRange(0, 60)
        self.ui_bubble_fade.setSuffix(" s")
        self.ui_bubble_fade.setSpecialValueText(self.i18n.t("dialogs.settings.bubble_never"))
        fade_sec = ui.get("bubble_fade_delay_ms", 4000) // 1000
        self.ui_bubble_fade.setValue(fade_sec)
        self._add_row(layout, self.i18n.t("dialogs.settings.bubble_duration"), self.ui_bubble_fade)

    def _build_appearance_hints(self, layout):
        hints = self.config.get("ui", {}).get("hints", {})

        self.ui_hints_enabled = QCheckBox(self.i18n.t("dialogs.settings.hints_enabled"))
        self.ui_hints_enabled.setChecked(hints.get("enabled", True))
        self.ui_hints_enabled.toggled.connect(self._on_hints_toggled)
        layout.addWidget(self.ui_hints_enabled)

        self.ui_hints_delay = QSpinBox()
        self.ui_hints_delay.setRange(0, 30000)
        self.ui_hints_delay.setSingleStep(500)
        self.ui_hints_delay.setSuffix(" ms")
        self.ui_hints_delay.setValue(hints.get("delay_ms", 2000))
        self.ui_hints_delay.setEnabled(self.ui_hints_enabled.isChecked())
        self._add_row(layout, self.i18n.t("dialogs.settings.hints_delay"), self.ui_hints_delay)

        reset_btn = QPushButton(self.i18n.t("dialogs.settings.hints_reset"))
        reset_btn.clicked.connect(self._on_reset_hints)
        layout.addWidget(reset_btn)

    def _on_hints_toggled(self, enabled):
        self.ui_hints_delay.setEnabled(enabled)

    # ── 2. Personaje (identidad) ─────────────────────────────────────────────

    def _build_character_page(self, layout):
        self._add_group(layout, "dialogs.settings.character_personality",
                        self._build_character_personality)
        self._add_group(layout, "dialogs.settings.character_mood", self._build_character_mood)
        layout.addStretch()

    # ── 2b. Packs (Sprite + Personalidad + Contexto) ───────────────────────

    def _build_packs_page(self, layout):
        self._add_group(layout, "dialogs.settings.character_sprite", self._build_character_sprite)
        self._add_group(layout, "dialogs.settings.character_packs", self._build_character_packs)
        self._add_group(layout, "dialogs.settings.packs_context", self._build_context_packs)
        layout.addStretch()

    def _build_character_sprite(self, layout):
        sprite_cfg = self.config.get("ui", {}).get("sprite", {})

        sprite_sel = QHBoxLayout()
        left_col = QVBoxLayout()

        self.sprite_list = QListWidget()
        self.sprite_list.setMaximumWidth(200)
        available = self._sprite_loader.list_available_sprites()
        for name in available:
            self.sprite_list.addItem(name)
        active = self._sprite_loader.get_active_sprite_name()
        items = self.sprite_list.findItems(active, Qt.MatchExactly)
        if items:
            self.sprite_list.setCurrentItem(items[0])
        self.sprite_list.currentTextChanged.connect(self._on_sprite_selected)
        left_col.addWidget(self.sprite_list)

        self.sprite_delete_btn = QPushButton(self.i18n.t("dialogs.settings.sprite_delete"))
        sel_name = self.sprite_list.currentItem()
        self.sprite_delete_btn.setEnabled(
            sel_name is not None and sel_name.text() != "default"
        )
        self.sprite_delete_btn.clicked.connect(self._on_delete_sprite)
        self.sprite_list.currentItemChanged.connect(self._on_sprite_item_changed)
        left_col.addWidget(self.sprite_delete_btn)

        sprite_sel.addLayout(left_col)

        preview_col = QVBoxLayout()
        self.sprite_preview = QLabel()
        self.sprite_preview.setFixedSize(150, 150)
        self.sprite_preview.setStyleSheet("background: transparent; border: 1px solid #555;")
        preview_col.addWidget(self.sprite_preview)

        self.ui_sprite_custom = QCheckBox(self.i18n.t("dialogs.settings.sprite_custom"))
        self.ui_sprite_custom.setChecked(sprite_cfg.get("use_custom", False))
        preview_col.addWidget(self.ui_sprite_custom)

        self.ui_sprite_path = QLineEdit(sprite_cfg.get("custom_path", "data/sprites/custom"))
        self.ui_sprite_path.setVisible(self.ui_sprite_custom.isChecked())
        self.ui_sprite_custom.toggled.connect(self.ui_sprite_path.setVisible)
        preview_col.addWidget(self.ui_sprite_path)

        self.ui_sprite_labels = QCheckBox(self.i18n.t("dialogs.settings.sprite_frame_labels"))
        self.ui_sprite_labels.setChecked(sprite_cfg.get("show_frame_labels", False))
        preview_col.addWidget(self.ui_sprite_labels)

        sprite_sel.addLayout(preview_col)
        layout.addLayout(sprite_sel)
        self._update_preview(active)

    def _build_character_personality(self, layout):
        pers = self.config.get("personality", {})
        self.pers_name = QLineEdit(pers.get("name", "Tomo"))
        self._add_row(layout, self.i18n.t("dialogs.settings.name"), self.pers_name)

        self.pers_traits = QLineEdit(pers.get("traits", "friendly, curious, helpful"))
        self._add_row(layout, self.i18n.t("dialogs.settings.traits"), self.pers_traits)

    def _build_character_mood(self, layout):
        pers = self.config.get("personality", {})
        mood_fields = [
            ("initial_happiness", "dialogs.settings.initial_happiness", 0.5),
            ("initial_energy", "dialogs.settings.initial_energy", 0.8),
            ("initial_curiosity", "dialogs.settings.initial_curiosity", 0.6),
            ("initial_closeness", "dialogs.settings.initial_closeness", 0.1),
            ("initial_connection", "dialogs.settings.initial_connection", 0.5),
        ]
        for key, label_key, default in mood_fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(self.i18n.t(label_key)))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            val = int(pers.get(key, default) * 100)
            slider.setValue(val)
            value_label = QLabel(f"{val}%")
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(f"{v}%"))
            row.addWidget(slider, stretch=1)
            row.addWidget(value_label)
            layout.addLayout(row)
            setattr(self, f"pers_{key}", slider)

    def _build_character_packs(self, layout):
        packs = self.config.get("personality_packs", {})

        self.pack_enabled = QCheckBox(self.i18n.t("dialogs.settings.pack_enabled"))
        self.pack_enabled.setChecked(packs.get("enabled", False))
        layout.addWidget(self.pack_enabled)

        self.pack_active = QComboBox()
        self.pack_active.setEditable(True)
        self._populate_pack_list(resolve_path(self.config, "personality_packs", "directory"))
        active = packs.get("active_pack")
        if active:
            idx = self.pack_active.findText(active)
            if idx >= 0:
                self.pack_active.setCurrentIndex(idx)
            else:
                self.pack_active.setCurrentText(active)
        self._add_row(layout, self.i18n.t("dialogs.settings.pack_active"), self.pack_active)

        path_row = QHBoxLayout()
        self.pack_directory = QLineEdit(packs.get("directory", "data/personality_packs"))
        path_row.addWidget(self.pack_directory, stretch=1)
        browse_btn = QPushButton(self.i18n.t("dialogs.settings.browse"))
        browse_btn.clicked.connect(self._on_browse_pack_dir)
        path_row.addWidget(browse_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        self._add_row(layout, self.i18n.t("dialogs.settings.pack_directory"), path_widget)

        btn_row = QHBoxLayout()
        reload_btn = QPushButton(self.i18n.t("dialogs.settings.pack_reload"))
        reload_btn.clicked.connect(self._on_reload_packs)
        btn_row.addWidget(reload_btn)

        self.pack_delete_btn = QPushButton(self.i18n.t("dialogs.settings.pack_delete"))
        self.pack_delete_btn.setEnabled(self.pack_active.currentIndex() >= 0)
        self.pack_delete_btn.clicked.connect(self._on_delete_pack)
        self.pack_active.currentIndexChanged.connect(
            lambda i: self.pack_delete_btn.setEnabled(i >= 0)
        )
        btn_row.addWidget(self.pack_delete_btn)

        layout.addLayout(btn_row)

    def _populate_pack_list(self, directory):
        self.pack_active.clear()
        pack_dir = Path(directory)
        if pack_dir.is_dir():
            for entry in sorted(pack_dir.iterdir()):
                if entry.is_dir() and (
                        (entry / "manifest.json").exists()
                        or (entry / "manifest.yaml").exists()):
                    self.pack_active.addItem(entry.name)
                elif entry.is_file() and entry.suffix == ".zip":
                    self.pack_active.addItem(entry.stem)

    # ── 2c. Context Packs ─────────────────────────────────────────────────

    def _build_context_packs(self, layout):
        context = self.config.setdefault("context", {})

        path_row = QHBoxLayout()
        self.ctx_directory = QLineEdit(context.get("directory", "data/context_packs"))
        path_row.addWidget(self.ctx_directory, stretch=1)
        browse_btn = QPushButton(self.i18n.t("dialogs.settings.browse"))
        browse_btn.clicked.connect(self._on_browse_context_dir)
        path_row.addWidget(browse_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        self._add_row(layout, self.i18n.t("dialogs.settings.context_directory"), path_widget)

        self.context_pack_list = QListWidget()
        self.context_pack_list.setMinimumHeight(140)
        self._populate_context_list()
        self.context_pack_list.itemChanged.connect(self._mark_dirty)
        self._add_row(layout, self.i18n.t("dialogs.settings.context_pack_list"),
                      self.context_pack_list)

        btn_row = QHBoxLayout()
        reload_btn = QPushButton(self.i18n.t("dialogs.settings.context_reload"))
        reload_btn.clicked.connect(self._on_reload_context_packs)
        btn_row.addWidget(reload_btn)

        self.context_pack_delete_btn = QPushButton(self.i18n.t("dialogs.settings.context_delete"))
        self.context_pack_delete_btn.setEnabled(False)
        self.context_pack_delete_btn.clicked.connect(self._on_delete_context_pack)
        self.context_pack_list.currentItemChanged.connect(
            lambda cur, prev: self.context_pack_delete_btn.setEnabled(cur is not None)
        )
        btn_row.addWidget(self.context_pack_delete_btn)

        layout.addLayout(btn_row)

    def _populate_context_list(self):
        self.context_pack_list.clear()
        for pack in self.context_manager.list_packs():
            text = pack["name"]
            if pack.get("version"):
                text += f" (v{pack['version']})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, pack["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if pack["active"] else Qt.Unchecked)
            self.context_pack_list.addItem(item)

    def _checked_context_ids(self):
        ids = []
        for i in range(self.context_pack_list.count()):
            item = self.context_pack_list.item(i)
            if item.checkState() == Qt.Checked:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _on_browse_context_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.t("dialogs.settings.context_directory"),
            str(user_resolve(self.ctx_directory.text())),
        )
        if path:
            self.ctx_directory.setText(path)
            self._on_reload_context_packs()

    def _on_reload_context_packs(self):
        self.context_manager.packs_dir = user_resolve(self.ctx_directory.text())
        self.context_manager.scan_packs()
        self._populate_context_list()

    def _on_delete_context_pack(self):
        item = self.context_pack_list.currentItem()
        if not item:
            return
        pack_id = item.data(Qt.UserRole)
        name = item.text()
        reply = QMessageBox.question(
            self,
            self.i18n.t("dialogs.settings.confirm_title"),
            self.i18n.t("dialogs.settings.context_delete_confirm", name=name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        pack = self.context_manager._packs.get(pack_id)
        if not pack:
            logger.warning(f"Context pack '{pack_id}' not found in manager")
            return
        try:
            path = pack.path
            if path.suffix == ".zip":
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            else:
                logger.warning(f"Unknown context pack path type: {path}")
                return
            logger.info(f"Deleted context pack: {name}")
            self.context_manager.scan_packs()
            self._populate_context_list()
            self.context_pack_delete_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Failed to delete context pack '{name}': {e}")
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.confirm_title"),
                str(e),
            )

    # ── 3. Mente ─────────────────────────────────────────────────────────────

    def _build_mind_page(self, layout):
        self._add_group(layout, "dialogs.settings.mind_llm", self._build_mind_llm)

        mg = QGroupBox(self.i18n.t("dialogs.settings.memory_general"))
        mg.setProperty("_search_text", self.i18n.t("dialogs.settings.memory_general").lower())
        mgl = QVBoxLayout(mg)
        mgl.setContentsMargins(12, 8, 12, 8)
        self._build_memory_general(mgl)
        layout.addWidget(mg)

        mc = QGroupBox(self.i18n.t("dialogs.settings.memory_chroma"))
        mc.setProperty("_search_text", self.i18n.t("dialogs.settings.memory_chroma").lower())
        mcl = QVBoxLayout(mc)
        mcl.setContentsMargins(12, 8, 12, 8)
        self._build_memory_chroma(mcl)
        layout.addWidget(mc)

        me = QGroupBox(self.i18n.t("dialogs.settings.memory_episodic"))
        me.setProperty("_search_text", self.i18n.t("dialogs.settings.memory_episodic").lower())
        mel = QVBoxLayout(me)
        mel.setContentsMargins(12, 8, 12, 8)
        self._build_memory_episodic(mel)
        layout.addWidget(me)

        layout.addStretch()

    def _build_mind_llm(self, layout):
        llm = self.config.get("llm", {})

        self.llm_provider = QComboBox()
        self.llm_provider.addItems(["ollama", "openai_compatible", "llama_cpp"])
        self.llm_provider.setCurrentText(llm.get("provider", "ollama"))
        self._add_row(layout, self.i18n.t("dialogs.settings.provider"), self.llm_provider)

        self.llm_model = QLineEdit(llm.get("model", "llama3.2:1b"))
        self._add_row(layout, self.i18n.t("dialogs.settings.model"), self.llm_model)

        self.llm_endpoint = QLineEdit(llm.get("endpoint", "http://localhost:11434"))
        self._add_row(layout, self.i18n.t("dialogs.settings.endpoint"), self.llm_endpoint)

        self.llm_api_key = QLineEdit(_creds.get_secret("llm_api_key") or "")
        self.llm_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._add_row(layout, self.i18n.t("dialogs.settings.api_key"), self.llm_api_key)

        self.llm_timeout = QSpinBox()
        self.llm_timeout.setRange(5, 300)
        self.llm_timeout.setSuffix("s")
        self.llm_timeout.setValue(llm.get("timeout", 60))
        self._add_row(layout, self.i18n.t("dialogs.settings.llm_timeout"), self.llm_timeout)

        self._build_llama_cpp(layout)

    def _build_llama_cpp(self, layout):
        llm_cpp = self.config.get("llm", {}).get("llama_cpp", {}) or {}

        path_row = QHBoxLayout()
        self.llama_path = QLineEdit(llm_cpp.get("model_path", ""))
        path_row.addWidget(self.llama_path, stretch=1)
        browse_btn = QPushButton(self.i18n.t("dialogs.settings.browse"))
        browse_btn.clicked.connect(self._on_browse_llama_path)
        path_row.addWidget(browse_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        self._add_row(layout, self.i18n.t("dialogs.settings.model_path"), path_widget)

        self.llama_ctx = QSpinBox()
        self.llama_ctx.setRange(256, 131072)
        self.llama_ctx.setSingleStep(512)
        self.llama_ctx.setValue(llm_cpp.get("n_ctx", 4096))
        self._add_row(layout, self.i18n.t("dialogs.settings.n_ctx"), self.llama_ctx)

        dl_row = QHBoxLayout()
        self.llama_download_btn = QPushButton(
            self.i18n.t("dialogs.settings.download_model")
        )
        self.llama_download_btn.clicked.connect(self._on_download_model)
        dl_row.addWidget(self.llama_download_btn, stretch=1)
        dl_widget = QWidget()
        dl_widget.setLayout(dl_row)
        self._add_row(layout, self.i18n.t("dialogs.settings.download_model_group"), dl_widget)

        note = QLabel(self.i18n.t("dialogs.settings.llama_license_note"))
        note.setWordWrap(True)
        layout.addWidget(note)

    def _on_browse_llama_path(self):
        current = self.llama_path.text().strip() or ""
        start = current if current else str(user_resolve("data/models"))
        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.t("dialogs.settings.model_path"), start, "GGUF (*.gguf)"
        )
        if path:
            self.llama_path.setText(path)

    def _on_download_model(self):
        from src.llm import download as dl

        dest = dl.model_path_from_config(self.config)
        if dest.exists():
            QMessageBox.information(
                self,
                self.i18n.t("dialogs.settings.title"),
                self.i18n.t("dialogs.settings.model_already_downloaded"),
            )
            return

        progress = QProgressDialog(
            self.i18n.t("dialogs.settings.download_progress_title"),
            self.i18n.t("dialogs.settings.cancel"),
            0, 100, self,
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        worker = _ModelDownloadWorker(self.config)

        def _on_progress(done, total):
            if total and total > 0:
                progress.setRange(0, 100)
                progress.setValue(int(done * 100 / total))
                progress.setLabelText(
                    f"{int(done * 100 / total)}% ({done}/{total} bytes)"
                )
            else:
                progress.setRange(0, 0)
                progress.setLabelText(f"{done} bytes")

        def _on_done(dest):
            progress.setValue(100)
            progress.close()
            self.llama_path.setText(str(dest))
            QMessageBox.information(
                self,
                self.i18n.t("dialogs.settings.title"),
                self.i18n.t("dialogs.settings.model_downloaded", path=dest),
            )

        def _on_error(error):
            if error == "cancelled":
                progress.close()
                return
            progress.close()
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.title"),
                self.i18n.t("dialogs.settings.model_download_error", error=error),
            )

        worker.progress.connect(_on_progress)
        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        progress.canceled.connect(worker.request_cancel)
        progress.show()
        worker.start()

    def _build_memory_general(self, layout):
        mem = self.config.get("memory", {})

        self.mem_short_term = QSpinBox()
        self.mem_short_term.setRange(1, 100)
        self.mem_short_term.setValue(mem.get("max_short_term_messages", 20))
        self._add_row(layout, self.i18n.t("dialogs.settings.max_short_term_messages"),
                      self.mem_short_term)

        self.mem_include_notes = QCheckBox(self.i18n.t("dialogs.settings.context_include_notes"))
        self.mem_include_notes.setChecked(mem.get("include_notes", True))
        layout.addWidget(self.mem_include_notes)

        clear_btn = QPushButton(self.i18n.t("dialogs.settings.memory_clear_all"))
        clear_btn.clicked.connect(self._on_clear_memories)
        layout.addWidget(clear_btn)

    def _build_memory_chroma(self, layout):
        mem = self.config.get("memory", {})

        path_row = QHBoxLayout()
        self.mem_chroma_path = QLineEdit(mem.get("chroma_persist_path", "./chroma_db"))
        path_row.addWidget(self.mem_chroma_path, stretch=1)
        browse_btn = QPushButton(self.i18n.t("dialogs.settings.browse"))
        browse_btn.clicked.connect(self._on_browse_chroma_path)
        path_row.addWidget(browse_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        self._add_row(layout, self.i18n.t("dialogs.settings.chroma_path"), path_widget)

        self.mem_embed_model = QComboBox()
        self.mem_embed_model.setEditable(True)
        known_models = [
            "all-MiniLM-L6-v2", "all-mpnet-base-v2",
            "BAAI/bge-small-en-v1.5", "intfloat/e5-small-v2",
        ]
        self.mem_embed_model.addItems(known_models)
        current = mem.get("embedding_model", "all-MiniLM-L6-v2")
        idx = self.mem_embed_model.findText(current)
        if idx >= 0:
            self.mem_embed_model.setCurrentIndex(idx)
        else:
            self.mem_embed_model.setCurrentText(current)
        self._add_row(layout, self.i18n.t("dialogs.settings.embedding_model"),
                      self.mem_embed_model)

        reindex_btn = QPushButton(self.i18n.t("dialogs.settings.memory_reindex"))
        reindex_btn.clicked.connect(self._on_reindex_notes)
        layout.addWidget(reindex_btn)

    def _build_memory_episodic(self, layout):
        mem = self.config.get("memory", {})

        self.mem_episodic_msg = QSpinBox()
        self.mem_episodic_msg.setRange(5, 50)
        self.mem_episodic_msg.setValue(mem.get("episodic_message_threshold", 15))
        self._add_row(layout, self.i18n.t("dialogs.settings.episodic_message_threshold"),
                      self.mem_episodic_msg)

        self.mem_episodic_threshold = self._labeled_slider(
            layout, self.i18n.t("dialogs.settings.episodic_auto_threshold"),
            0, 100, int(mem.get("episodic_auto_threshold", 0.6) * 100),
        )

        self.mem_auto_summary = QCheckBox(self.i18n.t("dialogs.settings.episodic_auto_summary"))
        self.mem_auto_summary.setChecked(mem.get("auto_session_summary", False))
        layout.addWidget(self.mem_auto_summary)

    # ── 4. Comportamiento ────────────────────────────────────────────────────

    def _build_behavior_page(self, layout):
        self._add_group(layout, "dialogs.settings.behavior_proactive", self._build_behavior_proactive)
        self._add_group(layout, "dialogs.settings.behavior_sleep", self._build_behavior_sleep)
        self._add_group(layout, "dialogs.settings.behavior_modes", self._build_behavior_modes)
        self._add_group(layout, "dialogs.settings.privacy_group", self._build_behavior_privacy)
        layout.addStretch()

    def _build_behavior_proactive(self, layout):
        modes = self.config.get("modes", {})

        self.proactive_cb = QCheckBox(self.i18n.t("dialogs.settings.enable_comments"))
        self.proactive_cb.setChecked(modes.get("proactive_comments", False))
        layout.addWidget(self.proactive_cb)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(60, 7200)
        self.cooldown_spin.setSuffix("s")
        self.cooldown_spin.setValue(modes.get("proactive_cooldown_seconds", 1800))
        self._add_row(layout, self.i18n.t("dialogs.settings.cooldown_label"), self.cooldown_spin)

        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 20)
        self.max_spin.setValue(modes.get("max_comments_per_hour", 2))
        self._add_row(layout, self.i18n.t("dialogs.settings.max_per_hour_label"), self.max_spin)

        self.prob_spin = self._labeled_slider(
            layout, self.i18n.t("dialogs.settings.random_prob_label"),
            0, 100, int(modes.get("comment_probability", 0.1) * 100),
        )

    def _build_behavior_sleep(self, layout):
        ui = self.config.get("ui", {})

        self.sleep_low_energy_cb = QCheckBox(
            self.i18n.t("dialogs.settings.sleep_low_energy")
        )
        self.sleep_low_energy_cb.setChecked(ui.get("sleep_low_energy_enabled", True))
        layout.addWidget(self.sleep_low_energy_cb)

        self.sleep_timeout_spin = QSpinBox()
        self.sleep_timeout_spin.setRange(30, 3600)
        self.sleep_timeout_spin.setSuffix(" s")
        self.sleep_timeout_spin.setValue(ui.get("sleep_timeout_seconds", 300))
        self._add_row(layout, self.i18n.t("dialogs.settings.sleep_timeout"),
                      self.sleep_timeout_spin)

    def _build_behavior_modes(self, layout):
        self.behavior_focus_cb = QCheckBox(self.i18n.t("dialogs.settings.behavior_focus_mode"))
        engine = getattr(self, "proactive_engine", None)
        if engine and hasattr(engine, "policy"):
            self.behavior_focus_cb.setChecked(
                getattr(engine.policy, "_focus_mode", False)
            )
        layout.addWidget(self.behavior_focus_cb)

        self.behavior_dnd_cb = QCheckBox(self.i18n.t("dialogs.settings.behavior_dnd_mode"))
        if engine and hasattr(engine, "policy"):
            self.behavior_dnd_cb.setChecked(
                getattr(engine.policy, "_dnd_mode", False)
            )
        layout.addWidget(self.behavior_dnd_cb)

    def _build_behavior_privacy(self, layout):
        privacy = self.config.setdefault("privacy", {})
        self.privacy_monitor_cb = QCheckBox(self.i18n.t("dialogs.settings.privacy_monitoring"))
        self.privacy_monitor_cb.setChecked(privacy.get("monitor_active_window", True))
        layout.addWidget(self.privacy_monitor_cb)

    # ── 5. Avanzado ──────────────────────────────────────────────────────────

    def _build_advanced_page(self, layout):
        self._add_group(layout, "dialogs.settings.advanced_sitting", self._build_advanced_sitting)
        self._add_group(layout, "dialogs.settings.advanced_database", self._build_advanced_database)
        self._add_group(layout, "dialogs.settings.advanced_logs", self._build_advanced_logs)
        self._add_group(layout, "dialogs.settings.advanced_about", self._build_advanced_about)
        layout.addStretch()

    def _build_advanced_sitting(self, layout):
        ws = self.config.get("window_sitting", {})

        self.ws_enabled = QCheckBox(self.i18n.t("dialogs.settings.ws_enabled"))
        self.ws_enabled.setChecked(ws.get("enabled", True))
        layout.addWidget(self.ws_enabled)

        self.ws_target = QComboBox()
        self.ws_target.addItems(["active_window", "desktop"])
        self.ws_target.setCurrentText(ws.get("target", "active_window"))
        self._add_row(layout, self.i18n.t("dialogs.settings.ws_target"), self.ws_target)

        self.ws_transition = self._labeled_slider(
            layout, self.i18n.t("dialogs.settings.ws_transition_speed"),
            0, 40, int(ws.get("transition_speed", 0.5) * 20),
        )

        self.ws_fallback = QComboBox()
        self.ws_fallback.addItems(["bottom-right", "bottom-left", "top-right", "top-left"])
        self.ws_fallback.setCurrentText(ws.get("fallback_position", "bottom-right"))
        self._add_row(layout, self.i18n.t("dialogs.settings.ws_fallback_position"),
                      self.ws_fallback)

    def _build_advanced_database(self, layout):
        db = self.config.get("database", {})

        self.db_path = QLineEdit(db.get("sqlite_path", "./data/tomodesk.db"))
        self.db_path.setReadOnly(True)
        self._add_row(layout, self.i18n.t("dialogs.settings.database_path"), self.db_path)

        btn_row = QHBoxLayout()
        compact_btn = QPushButton(self.i18n.t("dialogs.settings.db_compact"))
        compact_btn.clicked.connect(self._on_compact_db)
        btn_row.addWidget(compact_btn)

        export_btn = QPushButton(self.i18n.t("dialogs.settings.db_export"))
        export_btn.clicked.connect(self._on_export_memories)
        btn_row.addWidget(export_btn)

        import_btn = QPushButton(self.i18n.t("dialogs.settings.db_import"))
        import_btn.clicked.connect(self._on_import_memories)
        btn_row.addWidget(import_btn)

        layout.addLayout(btn_row)

    def _build_advanced_logs(self, layout):
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        level = self.config.get("logs", {}).get("level", "INFO")
        self.log_level.setCurrentText(level)
        self._add_row(layout, self.i18n.t("dialogs.settings.log_level"), self.log_level)

        open_log_btn = QPushButton(self.i18n.t("dialogs.settings.log_open_folder"))
        open_log_btn.clicked.connect(self._on_open_logs_folder)
        layout.addWidget(open_log_btn)

    def _build_advanced_about(self, layout):
        about_text = QLabel(
            self.i18n.t("app.about_text",
                        name=self.config["personality"]["name"],
                        model=self.config["llm"]["model"])
        )
        about_text.setWordWrap(True)
        layout.addWidget(about_text)

        tutorial_btn = QPushButton(self.i18n.t("dialogs.settings.tutorial_play"))
        tutorial_btn.clicked.connect(self._on_play_tutorial)
        layout.addWidget(tutorial_btn)

    # ── sprite helpers ───────────────────────────────────────────────────────

    def _on_sprite_selected(self, name: str):
        if name:
            self._update_preview(name)
            self.ui_sprite_custom.setChecked(False)
            self.ui_sprite_path.setEnabled(False)

    def _on_sprite_item_changed(self, current, previous):
        self.sprite_delete_btn.setEnabled(
            current is not None and current.text() != "default"
        )

    def _update_preview(self, name: str):
        pix = self._sprite_loader.get_preview(name)
        if pix and not pix.isNull():
            scaled = pix.scaled(140, 140,
                                Qt.KeepAspectRatio,
                                Qt.SmoothTransformation)
            self.sprite_preview.setPixmap(scaled)
        else:
            self.sprite_preview.clear()

    def _on_delete_sprite(self):
        item = self.sprite_list.currentItem()
        if not item:
            return
        name = item.text()
        reply = QMessageBox.question(
            self,
            self.i18n.t("dialogs.settings.confirm_title"),
            self.i18n.t("dialogs.settings.sprite_delete_confirm", name=name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        sprite_dir = self._sprite_loader.base_path / name
        if is_frozen():
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.confirm_title"),
                self.i18n.t(
                    "dialogs.settings.sprite_delete_bundled",
                    default="Bundled sprites cannot be deleted.",
                ),
            )
            return
        try:
            if sprite_dir.is_dir():
                shutil.rmtree(sprite_dir)
            logger.info(f"Deleted sprite: {name}")
            self._refresh_sprite_list()
            self.sprite_preview.clear()
        except Exception as e:
            logger.error(f"Failed to delete sprite '{name}': {e}")
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.confirm_title"),
                str(e),
            )

    def _refresh_sprite_list(self):
        self.sprite_list.currentItemChanged.disconnect(self._on_sprite_item_changed)
        self.sprite_list.clear()
        for name in self._sprite_loader.list_available_sprites():
            self.sprite_list.addItem(name)
        self.sprite_list.currentItemChanged.connect(self._on_sprite_item_changed)
        self.sprite_delete_btn.setEnabled(False)

    # ── action helpers ───────────────────────────────────────────────────────

    def _on_clear_memories(self):
        reply = QMessageBox.question(
            self,
            self.i18n.t("dialogs.settings.confirm_title"),
            self.i18n.t("dialogs.settings.confirm_clear_memories"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            from src.memory.memory import MemoryManager
            mm = getattr(self.parent(), "memory_manager", None)
            if mm:
                mm.clear_all_memories()
                logger.info("All memories cleared via settings")

    def _on_compact_db(self):
        from src.memory.database import DatabaseManager
        db_config = self.config.get("database", {}).get("sqlite_path", "./data/tomodesk.db")
        db_path = str(user_resolve(db_config))
        try:
            db = DatabaseManager(db_path)
            db.initialize()
            db.vacuum()
            logger.info(f"Database compacted: {db_path}")
            QMessageBox.information(
                self, self.i18n.t("dialogs.settings.confirm_title"),
                self.i18n.t("dialogs.settings.db_compact_done"),
            )
        except Exception as e:
            logger.error(f"Failed to compact database: {e}")

    def _on_export_memories(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("dialogs.settings.db_export"),
            str(Path.home() / "tomodesk_memories.json"),
            "JSON (*.json)",
        )
        if path:
            from src.memory.memory import MemoryManager
            mm = getattr(self.parent(), "memory_manager", None)
            if mm:
                try:
                    memories = mm.list_episodic_log()
                    import json as j
                    with open(path, "w", encoding="utf-8") as f:
                        j.dump(memories, f, indent=2, ensure_ascii=False)
                    logger.info(f"Exported {len(memories)} memories to {path}")
                except Exception as e:
                    logger.error(f"Export failed: {e}")

    def _on_import_memories(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.t("dialogs.settings.db_import"),
            str(Path.home()), "JSON (*.json)",
        )
        if path:
            import json as j
            try:
                with open(path, encoding="utf-8") as f:
                    memories = j.load(f)
                from src.memory.memory import MemoryManager
                mm = getattr(self.parent(), "memory_manager", None)
                if mm and isinstance(memories, list):
                    imported = 0
                    skipped = 0
                    for m in memories:
                        if not isinstance(m, dict):
                            skipped += 1
                            continue
                        summary = (m.get("summary") or "").strip()
                        if not summary:
                            skipped += 1
                            continue
                        importance = m.get("importance_score", 0.5)
                        if isinstance(importance, bool) or not isinstance(importance, (int, float)):
                            importance = 0.5
                        else:
                            importance = max(0.0, min(1.0, importance))
                        source = m.get("source", "import")
                        if not isinstance(source, str):
                            source = "import"
                        mm.add_episodic_memory(
                            summary=summary,
                            importance_score=importance,
                            source=source,
                        )
                        imported += 1
                    logger.info(f"Imported {imported}, skipped {skipped}")
            except Exception as e:
                logger.error(f"Import failed: {e}")

    def _on_open_logs_folder(self):
        dir_path = log_dir()
        dir_path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(dir_path))

    def _on_reset_hints(self):
        hints = self.config.setdefault("ui", {}).setdefault("hints", {})
        hints["dismissed"] = []
        logger.info("All hints reset")

    def _on_browse_pack_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.t("dialogs.settings.pack_directory"),
            str(user_resolve(self.pack_directory.text())),
        )
        if path:
            self.pack_directory.setText(path)
            self._on_reload_packs()

    def _on_reload_packs(self):
        self._populate_pack_list(user_resolve(self.pack_directory.text()))

    def _on_delete_pack(self):
        name = self.pack_active.currentText()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            self.i18n.t("dialogs.settings.confirm_title"),
            self.i18n.t("dialogs.settings.pack_delete_confirm", name=name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        engine = getattr(self, "proactive_engine", None)
        if not engine or not hasattr(engine, "pack_manager"):
            logger.warning("No pack manager available")
            return
        pm = engine.pack_manager
        pack = pm._packs.get(name)
        if not pack:
            logger.warning(f"Pack '{name}' not found in manager")
            return
        pack_path = pack["path"]
        try:
            if isinstance(pack_path, Path) and pack_path.suffix == ".zip":
                pack_path.unlink()
            elif pack_path.is_dir():
                shutil.rmtree(pack_path)
            else:
                logger.warning(f"Unknown pack path type: {pack_path}")
                return
            logger.info(f"Deleted pack: {name}")
            if pm._active_pack == name:
                pm.set_active_pack(None)
            pm.scan_packs()
            self._populate_pack_list(user_resolve(self.pack_directory.text()))
            self.pack_active.setCurrentIndex(-1)
            self.pack_delete_btn.setEnabled(False)
        except Exception as e:
            logger.error(f"Failed to delete pack '{name}': {e}")
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.confirm_title"),
                str(e),
            )

    def _on_browse_chroma_path(self):
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.t("dialogs.settings.chroma_path"),
            str(user_resolve(self.mem_chroma_path.text())),
        )
        if path:
            self.mem_chroma_path.setText(path)

    def _on_reindex_notes(self):
        from src.memory.memory import MemoryManager
        mm = getattr(self.parent(), "memory_manager", None)
        if mm and hasattr(mm, "reindex_notes"):
            try:
                mm.reindex_notes()
                logger.info("Notes reindexed")
                QMessageBox.information(
                    self, self.i18n.t("dialogs.settings.confirm_title"),
                    self.i18n.t("dialogs.settings.memory_reindex_done"),
                )
            except Exception as e:
                logger.error(f"Reindex failed: {e}")

    def _on_play_tutorial(self):
        parent = self.parent()
        if parent and hasattr(parent, "play_tutorial"):
            parent.play_tutorial()

    # ── setup ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("search_field")
        self._search_field.setPlaceholderText(self.i18n.t("dialogs.settings.search_placeholder"))
        self._search_field.textChanged.connect(self._apply_search)
        layout.addWidget(self._search_field)

        self._no_results_label = QLabel(self.i18n.t("dialogs.settings.no_results"))
        self._no_results_label.setObjectName("no_results")
        self._no_results_label.hide()
        layout.addWidget(self._no_results_label)

        split = QHBoxLayout()

        sidebar = QWidget()
        sidebar.setObjectName("settings_sidebar")
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(4, 4, 4, 4)
        self._nav = QListWidget()
        self._nav.setObjectName("settings_nav")
        self._nav.setFixedWidth(170)
        self._nav.setFocusPolicy(Qt.NoFocus)
        nav_layout.addWidget(self._nav)
        nav_layout.addStretch()
        split.addWidget(sidebar, 0)

        self._stack = QStackedWidget()
        split.addWidget(self._stack, 1)
        layout.addLayout(split, 1)

        self._pages = []
        self._add_nav_page("dialogs.settings.tab_appearance", self._build_appearance_page)
        self._add_nav_page("dialogs.settings.tab_packs", self._build_packs_page)
        self._add_nav_page("dialogs.settings.tab_character", self._build_character_page)
        self._add_nav_page("dialogs.settings.tab_behavior", self._build_behavior_page)
        self._add_nav_page("dialogs.settings.tab_mind", self._build_mind_page)
        self._add_nav_page("dialogs.settings.tab_advanced", self._build_advanced_page)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(self.i18n.t("dialogs.settings.save"))
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        self._close_btn = QPushButton(self.i18n.t("dialogs.settings.close"))
        self._close_btn.setObjectName("secondary")
        self._close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    def _add_nav_page(self, nav_key, builder):
        page, body_layout = self._make_page(nav_key)
        builder(body_layout)
        self._pages.append(page)
        self._stack.addWidget(page)
        self._nav.addItem(self.i18n.t(nav_key))

    def _apply_search(self, text):
        query = text.strip().lower()
        current_row = self._nav.currentRow()
        any_visible = False
        for idx, page in enumerate(self._pages):
            page_text = page.property("_search_text") or ""
            page_match = bool(query) and query in page_text
            groups = page.findChildren(QGroupBox)
            group_visible = 0
            for group in groups:
                group_text = group.property("_search_text") or ""
                matches = (not query) or page_match or query in group_text
                group.setVisible(matches)
                if matches:
                    group_visible += 1
            visible = (not query) or page_match or group_visible > 0
            item = self._nav.item(idx)
            item.setHidden(not visible)
            if visible:
                any_visible = True
        self._no_results_label.setVisible(bool(query) and not any_visible)
        if current_row >= 0:
            current = self._nav.item(current_row)
            if current.isHidden():
                for idx in range(self._nav.count()):
                    if not self._nav.item(idx).isHidden():
                        self._nav.setCurrentRow(idx)
                        break

    # ── dirty tracking ──────────────────────────────────────────────────────

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._update_close_button_text()

    def _update_close_button_text(self):
        key = "dialogs.settings.cancel" if self._dirty else "dialogs.settings.close"
        self._close_btn.setText(self.i18n.t(key))

    def _connect_dirty_tracking(self):
        widget_types = [QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QSlider, QLineEdit, QTextEdit]
        widgets = []
        for t in widget_types:
            widgets.extend(self.findChildren(t))
        for widget in widgets:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._mark_dirty)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox, QSlider)):
                widget.valueChanged.connect(self._mark_dirty)
            elif isinstance(widget, (QLineEdit, QTextEdit)):
                widget.textChanged.connect(self._mark_dirty)

    # ── save ─────────────────────────────────────────────────────────────────

    def _save_settings(self):
        self._save_appearance()
        self._save_character()
        if not self._save_mind():
            return
        self._save_behavior()
        self._save_advanced()
        self._save_context()

        save_config(self.config, get_config_path())

        self._apply_theme()
        self.close()

    def _save_appearance(self):
        ui = self.config.setdefault("ui", {})
        new_lang = self.ui_lang.currentText()
        old_lang = self.i18n.get_current_language()
        ui["language"] = new_lang
        resolved = self.i18n.detect_language(new_lang)
        if resolved != old_lang:
            self.i18n.set_language(resolved)
            self.language_changed.emit()
        ui["theme"] = self.ui_theme.currentText()
        ui["character_size"] = self.ui_char_size.value()
        ui["overlay_enabled"] = self.ui_overlay.isChecked()
        ui["overlay_default_position"] = self.ui_overlay_default.currentText()
        ui["overlay_opacity"] = self.ui_overlay_opacity.value() / 100.0
        ui["bubble_style"] = self.ui_bubble_style.currentText()
        ui["bubble_max_lines"] = self.ui_bubble_lines.value()
        ui["bubble_typewriter_interval_ms"] = self.ui_bubble_type.value()
        fade_val = self.ui_bubble_fade.value()
        ui["bubble_fade_delay_ms"] = fade_val * 1000 if fade_val > 0 else 0

        hints = ui.setdefault("hints", {})
        hints["enabled"] = self.ui_hints_enabled.isChecked()
        hints["delay_ms"] = self.ui_hints_delay.value()

    def _save_character(self):
        ui = self.config.setdefault("ui", {})
        sprite = ui.setdefault("sprite", {})
        sprite["use_custom"] = self.ui_sprite_custom.isChecked()
        sprite["custom_path"] = self.ui_sprite_path.text()
        sprite["show_frame_labels"] = self.ui_sprite_labels.isChecked()
        selected = self.sprite_list.currentItem()
        if selected and not sprite["use_custom"]:
            sprite["active"] = selected.text()
            sprite["custom_path"] = ""
        elif selected and sprite["use_custom"]:
            sprite["active"] = "custom"
        sprite_name = sprite.get("active", "default")
        self.sprite_changed.emit(sprite_name)

        pers = self.config.setdefault("personality", {})
        pers["name"] = self.pers_name.text()
        pers["traits"] = self.pers_traits.text()
        pers["initial_happiness"] = self.pers_initial_happiness.value() / 100.0
        pers["initial_energy"] = self.pers_initial_energy.value() / 100.0
        pers["initial_curiosity"] = self.pers_initial_curiosity.value() / 100.0
        pers["initial_closeness"] = self.pers_initial_closeness.value() / 100.0
        pers["initial_connection"] = self.pers_initial_connection.value() / 100.0

        packs = self.config.setdefault("personality_packs", {})
        packs["enabled"] = self.pack_enabled.isChecked()
        packs["active_pack"] = self.pack_active.currentText() or None
        packs["directory"] = self.pack_directory.text()

        engine = getattr(self, "proactive_engine", None)
        if engine and hasattr(engine, "pack_manager"):
            pm = engine.pack_manager
            pm.scan_packs()
            if packs["enabled"] and packs["active_pack"]:
                pm.set_active_pack(packs["active_pack"])
            else:
                pm.set_active_pack(None)

    def _save_mind(self):
        llm = self.config.setdefault("llm", {})
        llm["provider"] = self.llm_provider.currentText()
        llm["model"] = self.llm_model.text()
        llm["endpoint"] = self.llm_endpoint.text()
        llm["timeout"] = self.llm_timeout.value()

        if llm["provider"] == "openai_compatible" and not validate_llm_endpoint(llm["endpoint"]):
            logger.warning("Invalid LLM endpoint URL: %s", llm["endpoint"])
            QMessageBox.warning(
                self,
                self.i18n.t("dialogs.settings.title"),
                self.i18n.t("dialogs.settings.invalid_endpoint"),
            )
            return False

        api_key_value = self.llm_api_key.text()
        if api_key_value:
            _creds.set_secret("llm_api_key", api_key_value)
        else:
            _creds.delete_secret("llm_api_key")

        if "api_key" in llm:
            del llm["api_key"]

        llm.setdefault("llama_cpp", {})
        llm["llama_cpp"]["model_path"] = self.llama_path.text().strip() or \
            "data/models/llama-3.2-1B-Instruct-Q4_K_M.gguf"
        llm["llama_cpp"]["n_ctx"] = self.llama_ctx.value()

        mem = self.config.setdefault("memory", {})
        mem["max_short_term_messages"] = self.mem_short_term.value()
        mem["include_notes"] = self.mem_include_notes.isChecked()
        mem["chroma_persist_path"] = self.mem_chroma_path.text()
        mem["embedding_model"] = self.mem_embed_model.currentText()
        mem["episodic_message_threshold"] = self.mem_episodic_msg.value()
        mem["episodic_auto_threshold"] = self.mem_episodic_threshold.value() / 100.0
        mem["auto_session_summary"] = self.mem_auto_summary.isChecked()

        return True

    def _save_behavior(self):
        modes = self.config.setdefault("modes", {})
        modes["proactive_comments"] = self.proactive_cb.isChecked()
        modes["proactive_cooldown_seconds"] = self.cooldown_spin.value()
        modes["max_comments_per_hour"] = self.max_spin.value()
        modes["comment_probability"] = self.prob_spin.value() / 100.0

        ui = self.config.setdefault("ui", {})
        ui["sleep_low_energy_enabled"] = self.sleep_low_energy_cb.isChecked()
        ui["sleep_timeout_seconds"] = self.sleep_timeout_spin.value()

        engine = getattr(self, "proactive_engine", None)
        if engine and hasattr(engine, "policy"):
            engine.policy.set_focus_mode(self.behavior_focus_cb.isChecked())
            dnd = not self.behavior_dnd_cb.isChecked()
            engine.policy.set_dnd_mode(dnd)

        privacy = self.config.setdefault("privacy", {})
        privacy["monitor_active_window"] = self.privacy_monitor_cb.isChecked()

    def _save_advanced(self):
        ws = self.config.setdefault("window_sitting", {})
        ws["enabled"] = self.ws_enabled.isChecked()
        ws["target"] = self.ws_target.currentText()
        ws["transition_speed"] = self.ws_transition.value() / 20.0
        ws["fallback_position"] = self.ws_fallback.currentText()

        logs = self.config.setdefault("logs", {})
        logs["level"] = self.log_level.currentText()

    def _save_context(self):
        context = self.config.setdefault("context", {})
        directory = self.ctx_directory.text().strip() or "data/context_packs"
        context["directory"] = directory
        self.context_manager.packs_dir = user_resolve(directory)
        self.context_manager.scan_packs()
        self.context_manager.set_active_packs(self._checked_context_ids())

    # ── theme / reload ───────────────────────────────────────────────────────

    def _apply_theme(self):
        ui = self.config.setdefault("ui", {})
        new_theme = ui.get("theme", "light")
        styles = get_style_set(new_theme)
        self.setStyleSheet(styles["dialog"])

        new_size = self.config.get("ui", {}).get("character_size", 150)

        parent = self.parent()
        if parent and hasattr(parent, "apply_theme"):
            parent.apply_theme(new_theme, character_size=new_size)

        sprite_cfg = ui.get("sprite", {})
        if sprite_cfg.get("use_custom"):
            sprite_name = Path(sprite_cfg.get("custom_path", "")).name
        else:
            sprite_name = sprite_cfg.get("active", "default")
        if parent and hasattr(parent, "reload_sprite"):
            parent.reload_sprite(sprite_name)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            p = self.parent().geometry()
            self.move(
                p.x() + (p.width() - self.width()) // 2,
                p.y() + (p.height() - self.height()) // 2,
            )
