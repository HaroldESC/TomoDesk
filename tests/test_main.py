import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from main import _init_pack_manager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = PROJECT_ROOT / "data" / "locales"


def _spin_until(qapp, predicate, timeout: float = 5.0) -> bool:
    """Procesa eventos hasta que ``predicate`` sea cierto.

    El hilo del LLM avisa con un ``threading.Event`` y la señal llega en cola,
    así que hay que bombear el bucle: nada de ``time.sleep`` a pelo.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def mock_config():
    return {
        "personality": {"name": "Tomo"},
        "llm": {"model": "llama3.2:1b", "endpoint": "http://localhost:11434"},
        "modes": {},
    }


@pytest.fixture
def mock_memory_manager():
    return MagicMock()


def _real_i18n(lang: str = "en"):
    from src.config.i18n import I18nManager

    i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
    i18n.set_language(lang)
    return i18n


def _make_pack(directory, folder, name):
    pack_path = Path(directory) / folder
    pack_path.mkdir(parents=True, exist_ok=True)
    (pack_path / "manifest.json").write_text(json.dumps({
        "name": name,
        "format": "personality-pack-v1",
        "type": "personality",
    }), encoding="utf-8")


def _config(tmp_path, active=None, enabled=True):
    return {
        "personality": {"name": "Tomo"},
        "personality_packs": {
            "enabled": enabled,
            "active_pack": active,
            "directory": str(tmp_path),
        },
    }


class TestInitPackManager:
    def test_name_normalized_from_active_pack(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Lin"
        assert cfg["personality"]["name"] == "Lin"

    def test_legacy_folder_ref_normalized(self, tmp_path):
        _make_pack(tmp_path, "default", "Tomo")
        cfg = _config(tmp_path, active="Default")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Tomo"
        assert cfg["personality"]["name"] == "Tomo"

    def test_disabled_pack_keeps_manual_name(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin", enabled=False)
        pm = _init_pack_manager(cfg)
        assert pm._active_pack is None
        assert cfg["personality"]["name"] == "Tomo"


class TestInitWorker:
    """The init thread must report failures instead of hanging the splash."""

    def test_run_reports_error_instead_of_raising(self, monkeypatch):
        import main

        def _boom(_config):
            raise ValueError("Invalid LLM endpoint")

        monkeypatch.setattr(main, "_initialize", _boom)
        worker = main._build_init_worker_class()({"llm": {}})
        received = []
        worker.error.connect(received.append)
        worker.finished.connect(lambda deps: received.append(("finished", deps)))

        worker.run()

        assert received == ["Invalid LLM endpoint"]

    def test_run_emits_deps_on_success(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "_initialize", lambda cfg: {"ok": True})
        worker = main._build_init_worker_class()({"llm": {}})
        errors = []
        done = []
        worker.error.connect(errors.append)
        worker.finished.connect(done.append)

        worker.run()

        assert errors == []
        assert done == [{"ok": True}]

    def test_run_does_not_emit_finished_after_error(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "_initialize", lambda cfg: 1 / 0)
        worker = main._build_init_worker_class()({"llm": {}})
        events = []
        worker.finished.connect(lambda d: events.append("finished"))
        worker.error.connect(lambda m: events.append("error"))

        worker.run()

        assert events == ["error"]


class TestProviderLabel:
    """Every configured provider needs a human-readable error label."""

    def test_labels_by_provider(self):
        import main

        cases = {
            "ollama": "Ollama",
            "openai_compatible": "OpenAI",
            "llama_cpp": "llama.cpp",
            "custom": "custom",
        }
        for provider, expected in cases.items():
            config = {"llm": {"provider": provider, "endpoint": "http://x"}}
            label = main._provider_label(config)
            assert expected in label, f"{provider} -> {label}"

    def test_unknown_provider_returns_name(self):
        import main

        assert main._provider_label({"llm": {"provider": "weird"}}) == "weird"


class TestBackgroundMonitorStartup:
    """Los monitores deben arrancar ya con sus callbacks asignados."""

    def test_monitors_start_only_after_callbacks_are_wired(self):
        import main

        order = []

        class _Monitor:
            def __init__(self, name):
                self.name = name

            def set_trigger_callback(self, _cb):
                order.append(f"{self.name}:callback")

            def start(self):
                order.append(f"{self.name}:start")

        deps = {
            "event_monitor": _Monitor("events"),
            "reminder_checker": _Monitor("reminders"),
        }
        for name in ("event_monitor", "reminder_checker"):
            deps[name].set_trigger_callback(lambda *a: None)
        main._start_background_monitors(deps)

        assert order == ["events:callback", "reminders:callback",
                         "events:start", "reminders:start"]

    def test_start_background_monitors_starts_both(self):
        import main

        deps = {
            "event_monitor": MagicMock(),
            "reminder_checker": MagicMock(),
        }
        main._start_background_monitors(deps)
        deps["event_monitor"].start.assert_called_once_with()
        deps["reminder_checker"].start.assert_called_once_with()

    def test_start_background_monitors_tolerates_missing_services(self):
        import main
        from unittest.mock import MagicMock

        # Un dict vacio no tiene a quien arrancar, y un valor None se ignora.
        main._start_background_monitors({})
        none_monitor = MagicMock()
        main._start_background_monitors({"event_monitor": None})
        none_monitor.start.assert_not_called()


class TestMainWindowPositioning:
    """La ventana solo se centra en su primera aparicion."""

    def _window(self, config, memory_manager, i18n):
        from src.gui.windows.main_window import MainWindow

        return MainWindow(
            config=config, memory_manager=memory_manager, i18n=i18n
        )

    def test_first_show_centers_within_available_geometry(
        self, qapp, mock_config, mock_memory_manager, mock_i18n
    ):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry()

        window = self._window(mock_config, mock_memory_manager, mock_i18n)
        try:
            window.show()
            qapp.processEvents()
            # ``pos`` es la esquina del marco: es la que usa el calculo.
            expected = QPoint(
                available.x() + (available.width() - window.width()) // 2,
                available.y() + (available.height() - window.height()) // 2,
            )
            # El centrado se calcula con el area de cliente, pero ``pos()``
            # devuelve la esquina del marco. En plataformas con borde
            # (``offscreen`` añade 4 px) esas dos medidas no coinciden al
            # pixel: se tolera justo la diferencia real entre marco y cliente
            # mas 1 px por el redondeo entero de ``// 2``. La asercion sigue
            # siendo significativa: un centrado sobre ``geometry()`` (barra de
            # tareas incluida) desviaria la ventana decenas de pixeles.
            tolerance = 1 + max(
                window.frameGeometry().width() - window.width(),
                window.frameGeometry().height() - window.height(),
            )
            assert abs(window.pos().x() - expected.x()) <= tolerance
            assert abs(window.pos().y() - expected.y()) <= tolerance
        finally:
            window.close()

    def test_first_show_uses_available_geometry_not_full_geometry(
        self, qapp, mock_config, mock_memory_manager, mock_i18n, mocker
    ):
        from PySide6.QtCore import QRect
        from src.gui.windows import main_window as mw

        fake_screen = MagicMock()
        # ``geometry`` incluye la barra de tareas: centrarse en el area
        # completa dejaria la ventana fuera de la zona visible.
        fake_screen.geometry.return_value = QRect(0, 0, 1920, 1080)
        fake_screen.availableGeometry.return_value = QRect(0, 40, 1920, 1000)
        fake_app = MagicMock()
        fake_app.primaryScreen.return_value = fake_screen
        mocker.patch.object(mw, "QApplication", fake_app)

        window = self._window(mock_config, mock_memory_manager, mock_i18n)
        try:
            window.show()
            qapp.processEvents()
            expected_x = 0 + (1920 - window.width()) // 2
            expected_y = 40 + (1000 - window.height()) // 2
            assert window.pos().x() == expected_x
            assert window.pos().y() == expected_y
        finally:
            window.close()

    def test_second_show_keeps_user_position(
        self, qapp, mock_config, mock_memory_manager, mock_i18n
    ):
        from PySide6.QtCore import QPoint

        window = self._window(mock_config, mock_memory_manager, mock_i18n)
        try:
            window.show()
            qapp.processEvents()
            # Posicion elegida por el usuario, como tras arrastrar la ventana.
            window.move(QPoint(137, 211))
            window.hide()
            window.show()
            qapp.processEvents()
            assert window.pos() == QPoint(137, 211)
        finally:
            window.close()

    def test_repeated_show_never_recenters(
        self, qapp, mock_config, mock_memory_manager, mock_i18n
    ):
        window = self._window(mock_config, mock_memory_manager, mock_i18n)
        try:
            window.show()
            qapp.processEvents()
            first = window.pos()
            for _ in range(3):
                window.hide()
                window.show()
                qapp.processEvents()
            assert window.pos() == first
        finally:
            window.close()


def _prefs_manager(store: dict):
    """Memory manager de mentira con get/set_preference sobre un dict."""
    manager = MagicMock()
    manager.get_preference.side_effect = lambda key: store.get(key)
    manager.set_preference.side_effect = lambda key, value: store.__setitem__(
        key, value
    )
    return manager


class TestMainWindowGeometryPersistence:
    """B6.3: tamano y posicion de la ventana principal se recuerdan.

    Antes cada arranque volvia a 1000x700 centrada; ahora la geometria se
    guarda al ocultar a la bandeja y al salir, y se restaura al construir.
    """

    def _window(self, config, memory_manager, i18n):
        from src.gui.windows.main_window import MainWindow

        return MainWindow(
            config=config, memory_manager=memory_manager, i18n=i18n
        )

    def _expected_center(self, window):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QGuiApplication

        area = QGuiApplication.primaryScreen().availableGeometry()
        return QPoint(
            area.x() + (area.width() - window.width()) // 2,
            area.y() + (area.height() - window.height()) // 2,
        )

    def _center_tolerance(self, window):
        return 1 + max(
            window.frameGeometry().width() - window.width(),
            window.frameGeometry().height() - window.height(),
        )

    def test_geometry_is_saved_when_hiding_to_the_tray(
        self, qapp, mock_config, mock_i18n
    ):
        store = {}
        window = self._window(mock_config, _prefs_manager(store), mock_i18n)
        try:
            window.show()
            qapp.processEvents()
            window.move(120, 80)

            # ``_quit_on_close`` es False: cerrar oculta a la bandeja.
            window.close()

            assert store.get("window_geometry")
        finally:
            window.close()

    def test_geometry_is_saved_on_quit(self, qapp, mock_config, mock_i18n, mocker):
        from src.gui.windows import main_window as mw

        store = {}
        window = self._window(mock_config, _prefs_manager(store), mock_i18n)
        quit_mock = mocker.patch.object(mw.QApplication, "quit")
        try:
            window.show()
            qapp.processEvents()
            window.move(120, 80)

            window.quit_application()

            assert store.get("window_geometry")
            quit_mock.assert_called_once()
        finally:
            window.close()

    def test_unshown_window_does_not_persist_a_geometry(
        self, qapp, mock_config, mock_i18n
    ):
        """Sin haber sido posicionada no se guarda una geometria absurda."""
        store = {}
        window = self._window(mock_config, _prefs_manager(store), mock_i18n)
        try:
            window.close()
            assert "window_geometry" not in store
        finally:
            window.close()

    def test_geometry_is_restored_in_a_new_instance(
        self, qapp, mock_config, mock_i18n
    ):
        from PySide6.QtGui import QGuiApplication

        store = {}
        manager = _prefs_manager(store)

        first = self._window(mock_config, manager, mock_i18n)
        first.show()
        qapp.processEvents()
        first.move(150, 95)
        saved_size = first.size()
        first.close()

        second = self._window(mock_config, manager, mock_i18n)
        try:
            # Con geometria valida la ventana ya viene posicionada: no se
            # vuelve a centrar (``showEvent`` respeta lo guardado).
            assert second._positioned is True
            second.show()
            qapp.processEvents()

            # El eje vertical siempre cabe en la pantalla: se restaura exacto.
            assert second.pos().y() == 95
            # Y no es la posicion del centrado inicial.
            assert second.pos() != self._expected_center(second)
            # Si la ventana cabe a lo ancho (no es el caso en ``offscreen``,
            # con una pantalla de 800 px y un minimo de 900) la X tambien se
            # restaura; en caso contrario Qt la ajusta para que quepa.
            area = QGuiApplication.primaryScreen().availableGeometry()
            if area.width() >= saved_size.width():
                assert second.pos().x() == 150
        finally:
            first.close()
            second.close()

    def test_corrupt_geometry_falls_back_to_centering(
        self, qapp, mock_config, mock_i18n
    ):
        store = {"window_geometry": "no-es-base64-valido!"}
        window = self._window(mock_config, _prefs_manager(store), mock_i18n)
        try:
            assert window._positioned is False
            window.show()
            qapp.processEvents()
            expected = self._expected_center(window)
            tolerance = self._center_tolerance(window)
            assert abs(window.pos().x() - expected.x()) <= tolerance
            assert abs(window.pos().y() - expected.y()) <= tolerance
        finally:
            window.close()

    def test_empty_geometry_preference_falls_back_to_centering(
        self, qapp, mock_config, mock_i18n
    ):
        store = {"window_geometry": ""}
        window = self._window(mock_config, _prefs_manager(store), mock_i18n)
        try:
            assert window._positioned is False
            window.show()
            qapp.processEvents()
            expected = self._expected_center(window)
            tolerance = self._center_tolerance(window)
            assert abs(window.pos().x() - expected.x()) <= tolerance
            assert abs(window.pos().y() - expected.y()) <= tolerance
        finally:
            window.close()

    def test_missing_preference_keeps_centering_the_first_show(
        self, qapp, mock_config, mock_i18n
    ):
        window = self._window(mock_config, _prefs_manager({}), mock_i18n)
        try:
            assert window._positioned is False
            window.show()
            qapp.processEvents()
            expected = self._expected_center(window)
            tolerance = self._center_tolerance(window)
            assert abs(window.pos().x() - expected.x()) <= tolerance
            assert abs(window.pos().y() - expected.y()) <= tolerance
        finally:
            window.close()


class TestMainWindowStatusIcons:
    """Los iconos de la barra de estado son opcionales (ui.status_icons)."""

    def _window(self, qapp, config, memory_manager, i18n, state_manager,
                proactive_engine=None):
        from src.gui.windows.main_window import MainWindow

        return MainWindow(
            config=config,
            memory_manager=memory_manager,
            i18n=i18n,
            state_manager=state_manager,
            proactive_engine=proactive_engine,
        )

    def test_disabled_by_default_shows_plain_text(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("en"), mock_state_manager,
        )
        try:
            assert window.mood_label.text() == "Tomo is listening."
            assert window._mode_label.text() == ""
        finally:
            window.close()

    def test_disabled_default_matches_the_unprefixed_text(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        """Sin iconos ni un espacio inicial que desalinee la barra."""
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("en"), mock_state_manager,
        )
        try:
            assert not window.mood_label.text().startswith(" ")
            assert window.mood_label.text() == window.mood_label.text().lstrip()
        finally:
            window.close()

    def test_enabled_prefixes_the_mood_icon(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        mock_config.setdefault("ui", {})["status_icons"] = True
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("en"), mock_state_manager,
        )
        try:
            assert window.mood_label.text() == "\u2764\ufe0f Tomo is listening."
        finally:
            window.close()

    def test_mood_icon_follows_the_current_state(
        self, qapp, mock_config, mock_memory_manager
    ):
        from src.gui.styles.icons import ICON_RADIANT

        state = MagicMock()
        state.get_state.return_value = {
            "happiness": 0.95, "energy": 0.5, "curiosity": 0.1,
            "closeness": 0.1, "connection": 0.9,
        }
        mock_config.setdefault("ui", {})["status_icons"] = True
        window = self._window(
            qapp, mock_config, mock_memory_manager, _real_i18n("en"), state,
        )
        try:
            assert window.mood_label.text() == f"{ICON_RADIANT} Tomo is radiant today \u2728"
        finally:
            window.close()

    def test_unknown_state_falls_back_without_breaking(
        self, qapp, mock_config, mock_memory_manager
    ):
        from src.gui.styles import icons

        assert icons.status_icon("brand_new_state") == ""
        assert icons.icon("mode", "brand_new_mode") == ""
        assert icons.icon("no_such_family", "listening") == ""

    def test_mode_label_icons(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        from types import SimpleNamespace

        mock_config.setdefault("ui", {})["status_icons"] = True
        policy = MagicMock()
        policy.is_enabled.return_value = True
        policy.focus_mode = False
        engine = SimpleNamespace(policy=policy)
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("en"), mock_state_manager, engine,
        )
        try:
            # Sin foco ni DND solo se ve el icono de proactividad.
            assert window._mode_label.text() == "\U0001f514"

            policy.focus_mode = True
            window._update_status_message()
            assert window._mode_label.text() == "\U0001f3af \U0001f515 Focus"

            policy.focus_mode = False
            policy.is_enabled.return_value = False
            window._update_status_message()
            assert window._mode_label.text() == "\U0001f515 \U0001f507 DND"
        finally:
            window.close()

    def test_mode_label_unchanged_when_icons_are_off(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        from types import SimpleNamespace

        policy = MagicMock()
        policy.is_enabled.return_value = False
        policy.focus_mode = False
        engine = SimpleNamespace(policy=policy)
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("es"), mock_state_manager, engine,
        )
        try:
            assert window._mode_label.text() == "\U0001f507 No molestar"
        finally:
            window.close()

    def test_set_status_icons_enabled_changes_it_live(
        self, qapp, mock_config, mock_memory_manager, mock_state_manager
    ):
        window = self._window(
            qapp, mock_config, mock_memory_manager,
            _real_i18n("en"), mock_state_manager,
        )
        try:
            assert window._status_icons_enabled is False
            assert window.mood_label.text() == "Tomo is listening."

            window.set_status_icons_enabled(True)

            assert window._status_icons_enabled is True
            assert window.mood_label.text() == "\u2764\ufe0f Tomo is listening."

            window.set_status_icons_enabled(False)

            assert window.mood_label.text() == "Tomo is listening."
        finally:
            window.close()

    def test_missing_state_manager_keeps_the_bar_untouched(
        self, qapp, mock_config, mock_memory_manager
    ):
        window = self._window(
            qapp, mock_config, mock_memory_manager, _real_i18n("en"), None,
        )
        try:
            window.set_status_icons_enabled(True)  # must not raise
            assert window.mood_label.text() == ""
        finally:
            window.close()


class TestMainWindowSendButton:
    """El ancho del botón no debe bailar al pasar a "Pensando..."."""

    def _window(self, config, memory_manager, i18n):
        from src.gui.windows.main_window import MainWindow

        return MainWindow(config=config, memory_manager=memory_manager, i18n=i18n)

    def test_width_covers_the_widest_label(self, qapp, mock_config,
                                           mock_memory_manager):
        from PySide6.QtGui import QFontMetrics

        window = self._window(mock_config, mock_memory_manager, _real_i18n("en"))
        try:
            metrics = QFontMetrics(window.send_btn.font())
            for text in ("Send", "Thinking..."):
                assert window.send_btn.width() >= (
                    metrics.horizontalAdvance(text)
                ), text
        finally:
            window.close()

    def test_thinking_text_does_not_change_the_width(self, qapp, mock_config,
                                                     mock_memory_manager):
        window = self._window(mock_config, mock_memory_manager, _real_i18n("en"))
        try:
            before = window.send_btn.width()
            window.send_btn.setText(window.i18n.t("chat.thinking"))
            assert window.send_btn.width() == before
            assert window.send_btn.minimumWidth() == before
        finally:
            window.close()

    def test_width_is_recomputed_after_a_language_change(self, qapp, mock_config,
                                                         mock_memory_manager):
        window = self._window(mock_config, mock_memory_manager, _real_i18n("es"))
        try:
            window.i18n.set_language("es")
            window._apply_language()
            assert window.send_btn.width() >= window.send_btn.minimumWidth()
            assert window.send_btn.text() == "Enviar"
        finally:
            window.close()


class TestMainWindowChatInput:
    """Placeholder y tooltip del input salen de los locales."""

    def test_placeholder_has_no_ctrl_enter_and_tooltip_lists_commands(
        self, qapp, mock_config, mock_memory_manager
    ):
        from src.gui.windows.main_window import MainWindow

        window = MainWindow(
            config=mock_config,
            memory_manager=mock_memory_manager,
            i18n=_real_i18n("en"),
        )
        try:
            placeholder = window.input.placeholderText()
            assert "Ctrl+Enter" not in placeholder
            assert placeholder == "Type a message..."

            tooltip = window.input.toolTip()
            assert tooltip
            for command in ("/help", "/note", "/remind", "/memories", "/exit"):
                assert command in tooltip
        finally:
            window.close()

    def test_input_text_is_translated(
        self, qapp, mock_config, mock_memory_manager
    ):
        from src.gui.windows.main_window import MainWindow

        window = MainWindow(
            config=mock_config,
            memory_manager=mock_memory_manager,
            i18n=_real_i18n("es"),
        )
        try:
            assert window.input.placeholderText() == "Escribe un mensaje..."
            assert "/help" in window.input.toolTip()
        finally:
            window.close()


class _BlockingEngine:
    """Motor de mentira: se bloquea hasta que el test lo suelta."""

    def __init__(self, response="Respuesta del asistente", error=None):
        self.response = response
        self.error = error
        self.started = threading.Event()
        self.release = threading.Event()

    def chat(self, _text):
        self.started.set()
        self.release.wait(5)
        if self.error is not None:
            raise self.error
        return self.response


class TestMainWindowTypingIndicator:
    """El chat muestra "escribiendo..." mientras el LLM piensa (B4b)."""

    def _window(self, config, memory_manager, i18n, engine):
        from src.gui.windows.main_window import MainWindow

        return MainWindow(
            config=config,
            memory_manager=memory_manager,
            i18n=i18n,
            engine=engine,
        )

    def _typing_bubbles(self, window):
        return [
            bubble
            for bubble in window.chat._iter_bubbles()
            if bubble.property("_typing")
        ]

    def test_sending_shows_the_typing_bubble_until_the_answer(
        self, qapp, mock_config, mock_memory_manager
    ):
        engine = _BlockingEngine()
        window = self._window(
            mock_config, mock_memory_manager, _real_i18n("en"), engine
        )
        try:
            ready = window.chat.toPlainText().splitlines()
            window.input.setText("hola")
            window._send_message()

            assert engine.started.wait(5)
            assert window.chat.is_typing is True
            assert len(self._typing_bubbles(window)) == 1

            engine.release.set()
            assert _spin_until(
                qapp, lambda: "Respuesta del asistente" in window.chat.toPlainText()
            )

            assert window.chat.is_typing is False
            assert self._typing_bubbles(window) == []
            assert window.chat.toPlainText().splitlines() == ready + [
                "hola", "Respuesta del asistente",
            ]
        finally:
            engine.release.set()
            qapp.processEvents()
            window.close()

    def test_error_clears_the_typing_bubble(
        self, qapp, mock_config, mock_memory_manager
    ):
        engine = _BlockingEngine(error=RuntimeError("boom"))
        window = self._window(
            mock_config, mock_memory_manager, _real_i18n("en"), engine
        )
        try:
            window.input.setText("hola")
            window._send_message()

            assert engine.started.wait(5)
            assert window.chat.is_typing is True

            engine.release.set()
            assert _spin_until(qapp, lambda: "boom" in window.chat.toPlainText())

            assert window.chat.is_typing is False
            assert self._typing_bubbles(window) == []
        finally:
            engine.release.set()
            qapp.processEvents()
            window.close()

    def test_clear_chat_removes_the_typing_bubble(
        self, qapp, mock_config, mock_memory_manager
    ):
        engine = _BlockingEngine()
        window = self._window(
            mock_config, mock_memory_manager, _real_i18n("en"), engine
        )
        try:
            window.input.setText("hola")
            window._send_message()
            assert engine.started.wait(5)
            assert window.chat.is_typing is True

            window._clear_chat()

            assert window.chat.is_typing is False
            assert self._typing_bubbles(window) == []
            assert window.chat.toPlainText() == (
                "Chat cleared. Short-term memory reset."
            )
        finally:
            engine.release.set()
            qapp.processEvents()
            window.close()

    def test_typing_bubble_never_enters_the_history(
        self, qapp, mock_config, mock_memory_manager
    ):
        engine = _BlockingEngine()
        window = self._window(
            mock_config, mock_memory_manager, _real_i18n("en"), engine
        )
        try:
            ready = window.chat.toPlainText().splitlines()
            window.input.setText("hola")
            window._send_message()
            assert engine.started.wait(5)

            assert window.chat.toPlainText().splitlines() == ready + ["hola"]

            engine.release.set()
            assert _spin_until(qapp, lambda: not window.chat.is_typing)
        finally:
            engine.release.set()
            qapp.processEvents()
            window.close()