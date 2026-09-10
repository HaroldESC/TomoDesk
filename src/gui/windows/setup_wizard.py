"""Asistente de configuracion de primera ejecucion.

Se muestra una sola vez (cuando ``config.setup.completed`` es ``False``) y
permite elegir entre IA local (llama.cpp), una API externa compatible con
OpenAI, o posponer la decision. El diseno sigue el sistema de ``Design.md``:
texto via ``i18n.t`` y estilos de dialogo compartidos.
"""

import logging

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

from src.config.config import get_config_path, save_config, validate_llm_endpoint
from src.config.credentials import CredentialManager
from src.gui.styles.styles import get_style_set

logger = logging.getLogger(__name__)

MODE_LOCAL = "local"
MODE_EXTERNAL = "external"
MODE_LATER = "later"

_PAGE_WELCOME = 0
_PAGE_MODE = 1
_PAGE_LOCAL = 2
_PAGE_EXTERNAL = 3
_PAGE_FINISH = 4

# Workers desparentados al cerrar el asistente: se mantiene una referencia viva
# hasta que terminan para evitar destruir un QThread en ejecucion.
_ORPHAN_WORKERS: set = set()


def format_size(num_bytes: int) -> str:
    """Formatea bytes a una etiqueta legible (p.ej. ``3.8 GB``)."""
    if num_bytes is None or num_bytes < 0:
        return ""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return ""


class _DownloadWorker(QThread):
    """Descarga el GGUF del modelo recomendado sin bloquear la UI."""

    progress = Signal(int, int)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        from src.llm import download as dl

        try:
            dest = dl.download_model(
                self._config,
                progress=lambda done, total: self.progress.emit(done, total),
                should_cancel=lambda: self._cancelled,
            )
            self.done.emit(str(dest))
        except dl.DownloadCancelled:
            self.error.emit("cancelled")
        except Exception as exc:
            logger.exception("Fallo la descarga del modelo en el asistente")
            self.error.emit(str(exc))


class _SizeWorker(QThread):
    """Consulta el tamano remoto del modelo para la etiqueta informativa."""

    size_ready = Signal(int)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        from src.llm import download as dl

        self.size_ready.emit(dl.remote_content_length(self._url))


class SetupWizard(QDialog):
    def __init__(self, config, i18n=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.i18n = i18n
        self._download_worker = None
        self._size_worker = None
        self._size_started = False
        self._local_ready = False
        self._external_error = ""
        self._applied_mode = MODE_LATER
        self._alive = True

        theme = config.get("ui", {}).get("theme", "dark")
        self.setStyleSheet(get_style_set(theme)["dialog"])
        self.setWindowTitle(self._t("setup.title", "TomoDesk Setup"))
        self.setMinimumSize(580, 460)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_welcome_page())
        self._stack.addWidget(self._build_mode_page())
        self._stack.addWidget(self._build_local_page())
        self._stack.addWidget(self._build_external_page())
        self._stack.addWidget(self._build_finish_page())

        root = QVBoxLayout(self)
        root.addWidget(self._stack, stretch=1)
        root.addLayout(self._build_nav())

        self._stack.setCurrentIndex(_PAGE_WELCOME)
        self._sync_nav()

    # ── i18n ─────────────────────────────────────────────────────────────────

    def _t(self, key: str, fallback: str) -> str:
        if self.i18n is not None:
            text = self.i18n.t(key)
            if text != key:
                return text
        return fallback

    # ── pages ────────────────────────────────────────────────────────────────

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(self._t("setup.welcome_title", "Welcome to TomoDesk"))
        title.setObjectName("heading")
        layout.addWidget(title)

        body = QLabel(self._t(
            "setup.welcome_body",
            "Before starting, let's configure how TomoDesk will use AI. "
            "This only takes a moment.",
        ))
        body.setWordWrap(True)
        body.setObjectName("secondary")
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _build_mode_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(self._t("setup.mode_title", "How do you want to use AI?"))
        title.setObjectName("heading")
        layout.addWidget(title)

        self._mode_group = QButtonGroup(self)
        self._local_radio = self._add_mode_option(
            layout, self._mode_group, MODE_LOCAL,
            "setup.mode_local", "Local AI",
            "setup.mode_local_desc",
            "Run models directly on your computer. Conversations are not sent "
            "to an external service.",
        )
        self._external_radio = self._add_mode_option(
            layout, self._mode_group, MODE_EXTERNAL,
            "setup.mode_external", "External API",
            "setup.mode_external_desc",
            "Use an API such as OpenAI as your AI provider.",
        )
        self._later_radio = self._add_mode_option(
            layout, self._mode_group, MODE_LATER,
            "setup.mode_later", "Configure later",
            "setup.mode_later_desc",
            "Skip setup and decide later from Settings.",
        )
        self._local_radio.setChecked(True)
        layout.addStretch(1)
        return page

    def _add_mode_option(self, layout, group, mode, title_key, title_fb,
                         desc_key, desc_fb) -> QRadioButton:
        radio = QRadioButton(self._t(title_key, title_fb))
        radio.setProperty("setup_mode", mode)
        group.addButton(radio)
        layout.addWidget(radio)
        desc = QLabel(self._t(desc_key, desc_fb))
        desc.setWordWrap(True)
        desc.setObjectName("secondary")
        desc.setContentsMargins(24, 0, 0, 12)
        layout.addWidget(desc)
        return radio

    def _build_local_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(self._t("setup.local_title", "Local AI"))
        title.setObjectName("heading")
        layout.addWidget(title)

        layout.addWidget(QLabel(self._t("setup.local_engine", "Engine: llama.cpp")))

        from src.llm import download as dl
        llm_cpp = self.config.get("llm", {}).get("llama_cpp", {})
        self._model_file = llm_cpp.get("model_file") or dl.DEFAULT_MODEL_FILE
        self._model_url = dl.model_url_from_config(self.config)

        self._model_label = QLabel(self._t(
            "setup.local_model",
            "Recommended model: {model}",
        ).format(model=self._model_file))
        self._model_label.setWordWrap(True)
        layout.addWidget(self._model_label)

        self._size_label = QLabel(self._t(
            "setup.local_size", "Approximate size: {size}"
        ).format(size="..."))
        self._size_label.setObjectName("secondary")
        layout.addWidget(self._size_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName("secondary")
        layout.addWidget(self._status_label)

        self._download_btn = QPushButton(self._t("setup.download", "Download"))
        self._download_btn.setObjectName("primary")
        self._download_btn.clicked.connect(self._start_download)
        layout.addWidget(self._download_btn)

        self._skip_label = QLabel(self._t(
            "setup.skip_download",
            "You can download the model later from Settings.",
        ))
        self._skip_label.setWordWrap(True)
        self._skip_label.setObjectName("secondary")
        layout.addWidget(self._skip_label)

        layout.addStretch(1)
        return page

    def _build_external_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(self._t("setup.external_title", "External API"))
        title.setObjectName("heading")
        layout.addWidget(title)

        layout.addWidget(QLabel(self._t("setup.external_endpoint", "Endpoint")))
        self._endpoint_edit = QLineEdit(
            self.config.get("llm", {}).get("endpoint", "") or ""
        )
        self._endpoint_edit.setPlaceholderText("https://api.openai.com/v1")
        layout.addWidget(self._endpoint_edit)

        layout.addWidget(QLabel(self._t("setup.external_model", "Model")))
        self._model_edit = QLineEdit(self.config.get("llm", {}).get("model", "") or "")
        self._model_edit.setPlaceholderText("gpt-4o-mini")
        layout.addWidget(self._model_edit)

        layout.addWidget(QLabel(self._t("setup.external_api_key", "API key (optional)")))
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self._api_key_edit)

        self._external_error_label = QLabel("")
        self._external_error_label.setWordWrap(True)
        self._external_error_label.setObjectName("error")
        self._external_error_label.setVisible(False)
        layout.addWidget(self._external_error_label)

        layout.addStretch(1)
        return page

    def _build_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(self._t("setup.finish_title", "All set"))
        title.setObjectName("heading")
        layout.addWidget(title)

        self._finish_label = QLabel(self._t("setup.finish_body", "TomoDesk will now start."))
        self._finish_label.setWordWrap(True)
        self._finish_label.setObjectName("secondary")
        layout.addWidget(self._finish_label)

        layout.addStretch(1)
        return page

    def _build_nav(self) -> QHBoxLayout:
        nav = QHBoxLayout()
        self._cancel_btn = QPushButton(self._t("setup.cancel", "Cancel"))
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.clicked.connect(self._on_cancel)
        nav.addWidget(self._cancel_btn)

        nav.addStretch(1)

        self._back_btn = QPushButton(self._t("setup.back", "Back"))
        self._back_btn.setObjectName("secondary")
        self._back_btn.clicked.connect(self._on_back)
        nav.addWidget(self._back_btn)

        self._next_btn = QPushButton(self._t("setup.next", "Next"))
        self._next_btn.setObjectName("primary")
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._next_btn)
        return nav

    # ── navigation ───────────────────────────────────────────────────────────

    def selected_mode(self) -> str:
        for radio in (
            self._local_radio, self._external_radio, self._later_radio,
        ):
            if radio.isChecked():
                return radio.property("setup_mode")
        return MODE_LATER

    def _sync_nav(self) -> None:
        index = self._stack.currentIndex()
        self._back_btn.setEnabled(index in (_PAGE_MODE, _PAGE_LOCAL, _PAGE_EXTERNAL))
        if index == _PAGE_FINISH:
            self._next_btn.setText(self._t("setup.finish", "Finish"))
        else:
            self._next_btn.setText(self._t("setup.next", "Next"))
        self._sync_summary()

    def _sync_summary(self) -> None:
        if self._stack.currentIndex() != _PAGE_FINISH:
            return
        mode = self.selected_mode()
        if mode == MODE_LOCAL:
            key, fb = "setup.finish_local", "Local AI with llama.cpp is ready."
        elif mode == MODE_EXTERNAL:
            key, fb = "setup.finish_external", "External API configured."
        else:
            key, fb = "setup.finish_later", "You can configure AI later from Settings."
        self._finish_label.setText(self._t(key, fb))

    def _on_next(self) -> None:
        index = self._stack.currentIndex()
        if index == _PAGE_WELCOME:
            self._go(_PAGE_MODE)
        elif index == _PAGE_MODE:
            mode = self.selected_mode()
            if mode == MODE_LOCAL:
                self._go(_PAGE_LOCAL)
            elif mode == MODE_EXTERNAL:
                self._go(_PAGE_EXTERNAL)
            else:
                self._go(_PAGE_FINISH)
        elif index == _PAGE_LOCAL:
            self._go(_PAGE_FINISH)
        elif index == _PAGE_EXTERNAL:
            if self._validate_external():
                self._go(_PAGE_FINISH)
        elif index == _PAGE_FINISH:
            self._finish()

    def _on_back(self) -> None:
        index = self._stack.currentIndex()
        if index == _PAGE_MODE:
            self._go(_PAGE_WELCOME)
        elif index in (_PAGE_LOCAL, _PAGE_EXTERNAL):
            self._go(_PAGE_MODE)
        elif index == _PAGE_FINISH:
            self._go(self._finish_back_target())

    def _finish_back_target(self) -> int:
        mode = self.selected_mode()
        if mode == MODE_LOCAL:
            return _PAGE_LOCAL
        if mode == MODE_EXTERNAL:
            return _PAGE_EXTERNAL
        return _PAGE_MODE

    def _go(self, index: int) -> None:
        if index == _PAGE_LOCAL:
            self._start_size_probe()
        self._stack.setCurrentIndex(index)
        self._sync_nav()

    def _validate_external(self) -> bool:
        endpoint = self._endpoint_edit.text().strip()
        model = self._model_edit.text().strip()
        error = ""
        if not validate_llm_endpoint(endpoint):
            error = self._t(
                "setup.external_invalid_endpoint",
                "Enter a valid http(s) endpoint.",
            )
        elif not model:
            error = self._t(
                "setup.external_missing_model", "Enter a model name."
            )
        self._external_error = error
        self._external_error_label.setText(error)
        self._external_error_label.setVisible(bool(error))
        return not error

    # ── size probe ───────────────────────────────────────────────────────────

    def _start_size_probe(self) -> None:
        if self._size_started:
            return
        self._size_started = True
        worker = _SizeWorker(self._model_url, parent=self)
        self._size_worker = worker
        worker.size_ready.connect(self._on_size_ready)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_size_ready(self, size: int) -> None:
        if not self._alive:
            return
        label = format_size(size)
        if not label:
            label = self._t("setup.local_size_unknown", "unknown")
        self._size_label.setText(self._t(
            "setup.local_size", "Approximate size: {size}"
        ).format(size=label))

    # ── download ─────────────────────────────────────────────────────────────

    def _start_download(self) -> None:
        from src.llm import download as dl

        dest = dl.model_path_from_config(self.config)
        if dest.exists():
            self._local_ready = True
            self._status_label.setText(self._t("setup.downloaded", "Model ready"))
            self._download_btn.setEnabled(False)
            return

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._download_btn.setEnabled(False)
        self._status_label.setText(self._t("setup.downloading", "Downloading model..."))

        worker = _DownloadWorker(self.config, parent=self)
        self._download_worker = worker
        worker.progress.connect(self._on_download_progress)
        worker.done.connect(self._on_download_done)
        worker.error.connect(self._on_download_error)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_download_progress(self, done: int, total: int) -> None:
        if not self._alive:
            return
        if total and total > 0:
            percent = int(done * 100 / total)
            self._progress.setRange(0, 100)
            self._progress.setValue(percent)
            self._status_label.setText(self._t(
                "setup.downloading_percent", "Downloading model... {percent}%"
            ).format(percent=percent))
        else:
            self._progress.setRange(0, 0)
            self._status_label.setText(self._t(
                "setup.downloading", "Downloading model..."
            ))

    def _on_download_done(self, dest: str) -> None:
        if not self._alive:
            return
        self._local_ready = True
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._status_label.setText(self._t("setup.downloaded", "Model ready"))
        self._download_btn.setEnabled(False)

    def _on_download_error(self, error: str) -> None:
        if not self._alive:
            return
        self._progress.setVisible(False)
        self._download_btn.setEnabled(True)
        if error == "cancelled":
            self._status_label.setText(self._t(
                "setup.download_cancelled", "Download cancelled"
            ))
            return
        logger.error("Descarga del modelo fallida: %s", error)
        self._status_label.setText(self._t(
            "setup.download_error", "Download failed: {error}"
        ).format(error=error))

    def _on_cancel(self) -> None:
        if self._download_worker is not None and self._download_worker.isRunning():
            self._download_worker.request_cancel()
            self._download_worker.wait(2000)
            return
        self.reject()

    def closeEvent(self, event) -> None:
        self._alive = False
        self._detach_workers()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self._alive = False
        self._detach_workers()
        super().done(result)

    def _detach_workers(self) -> None:
        """Saca de la jerarquia los QThread en ejecucion para poder cerrar sin
        destruirlos a mitad de trabajo; terminan solos y se limpian via
        ``finished``."""
        for worker in (self._size_worker, self._download_worker):
            if worker is None or not worker.isRunning():
                continue
            if hasattr(worker, "request_cancel"):
                worker.request_cancel()
            worker.setParent(None)
            _ORPHAN_WORKERS.add(worker)
            worker.finished.connect(
                lambda w=worker: _ORPHAN_WORKERS.discard(w)
            )

    # ── apply ────────────────────────────────────────────────────────────────

    def _finish(self) -> None:
        self.apply_to_config()
        self.accept()

    def apply_to_config(self) -> None:
        mode = self.selected_mode()
        llm = self.config.setdefault("llm", {})
        if mode == MODE_LOCAL:
            llm["provider"] = "llama_cpp"
        elif mode == MODE_EXTERNAL:
            llm["provider"] = "openai_compatible"
            llm["endpoint"] = self._endpoint_edit.text().strip()
            llm["model"] = self._model_edit.text().strip()
            api_key = self._api_key_edit.text().strip()
            if api_key:
                CredentialManager().set_secret("llm_api_key", api_key)
        self.config.setdefault("setup", {})["completed"] = True
        self._applied_mode = mode
        try:
            save_config(self.config, get_config_path())
        except Exception:
            logger.exception("No se pudo guardar la configuracion tras el asistente")

    def requires_restart(self) -> bool:
        """True si el asistente cambio el proveedor LLM y hace falta reiniciar."""
        return self._applied_mode in (MODE_LOCAL, MODE_EXTERNAL)
