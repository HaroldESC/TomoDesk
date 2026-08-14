import atexit
import os
import sys
import threading
import logging
import argparse

os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


def _init_i18n(config):
    from src.config.i18n import I18nManager
    i = I18nManager(config.get("paths", {}).get("locales", "data/locales"), default_lang="en")
    lang = i.detect_language(config.get("ui", {}).get("language", "auto"))
    i.set_language(lang)
    return i


def _init_db(config):
    from src.memory.database import DatabaseManager
    db = DatabaseManager(config["database"]["sqlite_path"])
    db.initialize()
    return db


def _init_chroma(config):
    from src.memory.chroma_manager import ChromaManager
    cm = ChromaManager(
        config["memory"]["chroma_persist_path"],
        config["memory"]["embedding_model"],
    )
    cm.initialize()
    return cm


def _init_pack_manager(config):
    from src.personality.personality_pack import PersonalityPackManager
    pm = PersonalityPackManager(
        config.get("personality_packs", {}).get("directory", "data/personality_packs")
    )
    pm.scan_packs()
    active_pack = config.get("personality_packs", {}).get("active_pack")
    if active_pack:
        pm.set_active_pack(active_pack)
    return pm


def _init_event_monitor(memory_manager, config, state_manager):
    from src.core.events import EventMonitor
    em = EventMonitor(memory_manager, config, poll_interval=2.0)
    em.set_state_manager(state_manager)
    em.start()
    return em


def _init_reminder_checker(memory_manager, config):
    from src.system.reminder_checker import ReminderChecker
    rc = ReminderChecker(memory_manager, config, check_interval=30.0)
    rc.start()
    return rc


def _initialize(config):
    global _db_manager
    from src.memory.memory import MemoryManager
    from src.core.state import StateManager
    from src.llm.proactive_policy import ProactivePolicy
    from src.personality.comment_loader import CommentLoader
    from src.llm.llm import create_provider
    from src.core.context import ContextBuilder
    from src.llm.proactive_engine import ProactiveEngine
    from src.llm.prompts import PromptBuilder
    from src.memory.episodic_summarizer import EpisodicSummarizer
    from src.core.conversation import ConversationEngine

    with ThreadPoolExecutor(max_workers=5) as pool:
        fut_i18n = pool.submit(_init_i18n, config)
        fut_db = pool.submit(_init_db, config)
        fut_chroma = pool.submit(_init_chroma, config)
        fut_pack = pool.submit(_init_pack_manager, config)

    i18n = fut_i18n.result()
    db_manager = fut_db.result()
    _db_manager = db_manager
    atexit.register(_close_db)
    chroma_manager = fut_chroma.result()

    memory_manager = MemoryManager(db_manager, chroma_manager, config)

    state_manager = StateManager(config)
    state_manager.load_from_preferences(memory_manager)

    pack_manager = fut_pack.result()
    proactive_policy = ProactivePolicy(config)

    comment_loader = CommentLoader(
        config.get("paths", {}).get("comments_yaml", "data/comments.yaml"),
        i18n=i18n,
    )

    from src.config.credentials import CredentialManager
    _creds = CredentialManager()
    _api_key = _creds.get_secret("llm_api_key") or config.get("llm", {}).get("api_key")

    # Parallel phase 2: components that depend only on memory_manager
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_events = pool.submit(_init_event_monitor, memory_manager, config, state_manager)
        fut_reminder = pool.submit(_init_reminder_checker, memory_manager, config)
        fut_provider = pool.submit(create_provider, config, _api_key)

    event_monitor = fut_events.result()
    reminder_checker = fut_reminder.result()
    provider = fut_provider.result()

    context_builder = ContextBuilder(config, memory_manager, event_monitor=event_monitor)

    proactive_engine = ProactiveEngine(
        comment_loader, proactive_policy, memory_manager, config,
        pack_manager=pack_manager,
    )
    event_monitor.set_trigger_callback(proactive_engine.handle_trigger)
    proactive_engine.start_random_timer()

    prompt_builder = PromptBuilder(config, context_builder, memory_manager, i18n=i18n)

    episodic_summarizer = EpisodicSummarizer(memory_manager, provider, config)
    engine = ConversationEngine(
        provider, prompt_builder, memory_manager, config,
        state_manager=state_manager, episodic_summarizer=episodic_summarizer,
    )

    deps = {
        "config": config,
        "memory_manager": memory_manager,
        "state_manager": state_manager,
        "event_monitor": event_monitor,
        "reminder_checker": reminder_checker,
        "context_builder": context_builder,
        "proactive_engine": proactive_engine,
        "engine": engine,
        "i18n": i18n,
    }
    _validate_run_deps(deps)
    return deps


_REQUIRED_RUN_KEYS: set = {
    "config", "memory_manager", "state_manager", "event_monitor",
    "reminder_checker", "context_builder", "proactive_engine", "engine", "i18n",
}


def _validate_run_deps(deps: dict) -> None:
    missing = _REQUIRED_RUN_KEYS - deps.keys()
    if missing:
        raise KeyError(f"Missing required dependencies: {missing}")
    extra = deps.keys() - _REQUIRED_RUN_KEYS
    if extra:
        raise KeyError(f"Unexpected dependencies: {extra}")


def _check_ollama(engine, state_manager, memory_manager, proactive_engine, reminder_checker, event_monitor):
    if engine.check_availability():
        return True
    state_manager.save_to_preferences(memory_manager)
    proactive_engine.stop_random_timer()
    reminder_checker.stop()
    event_monitor.stop()
    return False


def _graceful_shutdown(deps: dict) -> None:
    stops = [
        ("proactive_engine", "stop_random_timer"),
        ("reminder_checker", "stop"),
        ("event_monitor", "stop"),
    ]
    for name, method in stops:
        obj = deps.get(name)
        if obj is not None and hasattr(obj, method):
            try:
                getattr(obj, method)()
            except Exception:
                logger.exception("Failed to stop %s during shutdown", name)

    if not deps.get("_summary_started"):
        deps["_summary_started"] = True
        engine = deps.get("engine")
        if engine is not None and hasattr(engine, "summarize_session"):
            summarize_thread = threading.Thread(
                target=engine.summarize_session, daemon=True
            )
            summarize_thread.start()
            summarize_thread.join(timeout=0.5)

    state_manager = deps.get("state_manager")
    memory_manager = deps.get("memory_manager")
    if (
        state_manager is not None
        and memory_manager is not None
        and not deps.get("_prefs_saved")
    ):
        try:
            state_manager.save_to_preferences(memory_manager)
            deps["_prefs_saved"] = True
        except Exception:
            logger.exception("Failed to save preferences during shutdown")


def _show_splash():
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPixmap
    from PySide6.QtCore import Qt
    pix = QPixmap(320, 140)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(30, 30, 46, 220))
    p.setPen(QColor(137, 180, 250, 100))
    p.drawRoundedRect(1, 1, 318, 138, 16, 16)
    p.setPen(QColor("#cdd6f4"))
    p.setFont(QFont("Segoe UI", 18, QFont.Bold))
    fm = QFontMetrics(p.font())
    t1 = "TomoDesk"
    t2 = "Cargando..."
    r1 = fm.boundingRect(pix.rect(), Qt.AlignCenter, t1)
    p.drawText(pix.rect().adjusted(0, -12, 0, 0), Qt.AlignCenter, t1)
    p.setFont(QFont("Segoe UI", 13))
    p.setPen(QColor("#a6adc8"))
    p.drawText(pix.rect().adjusted(0, 16, 0, 0), Qt.AlignCenter, t2)
    p.end()
    splash = QSplashScreen(pix, Qt.FramelessWindowHint)
    splash.setAttribute(Qt.WA_TranslucentBackground)
    screen = QApplication.primaryScreen().geometry()
    splash.move(screen.center().x() - 160, screen.center().y() - 70)
    splash.show()
    QApplication.processEvents()
    return splash


class _InitWorker(QThread):
    finished = Signal(dict)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config

    def run(self):
        deps = _initialize(self._config)
        self.finished.emit(deps)


def run_gui(config):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tomodesk.tomo.1.0")
    except (ImportError, AttributeError, OSError):
        pass

    splash = _show_splash()

    from src.gui.styles.styles import MAIN_STYLE
    app.setStyleSheet(MAIN_STYLE)

    _restart_pending = False
    deps_ref = {"deps": None}

    def _on_init_complete(deps):
        nonlocal _restart_pending
        deps_ref["deps"] = deps
        splash.close()
        engine = deps["engine"]
        i18n = deps["i18n"]

        overlay_ref = {"overlay": None}

        def on_proactive_comment(comment: str, trigger_type: str):
            ov = overlay_ref["overlay"]
            if ov:
                ov._bubble_text_signal.emit(comment, False)

        deps["proactive_engine"].set_delivery_callback(on_proactive_comment)

        def on_reminder(message: str):
            print(f"\n[REMINDER] {message}")
            ov = overlay_ref["overlay"]
            if ov:
                ov._bubble_text_signal.emit(message, False)

        deps["reminder_checker"].set_callback(on_reminder)

        from src.gui.windows.overlay_window import OverlayWindow
        overlay = OverlayWindow(memory_manager=deps["memory_manager"], i18n=i18n, config=config,
                                pack_manager=deps["proactive_engine"].pack_manager,
                                state_manager=deps["state_manager"],
                                event_monitor=deps["event_monitor"])
        overlay_ref["overlay"] = overlay

        from src.gui.windows.main_window import MainWindow
        window = MainWindow(**deps, overlay=overlay)
        window.show()

        def _bring_chat_to_front():
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
            window.show()
            window.raise_()
            window.activateWindow()
            QTimer.singleShot(100, window.raise_)
            QTimer.singleShot(100, window.activateWindow)

        overlay.set_context_menu_callbacks({
            "chat":      _bring_chat_to_front,
            "notes":     window.open_notes,
            "reminders": window.open_reminders,
            "memories":  window._open_memories,
            "settings":  window._open_settings,
            "exit":      window.quit_application,
        })

        from PySide6.QtCore import QCoreApplication
        def restart_app():
            nonlocal _restart_pending
            _restart_pending = True
            _graceful_shutdown(deps)
            window._quit_on_close = True
            overlay.close()
            window.close()
            QCoreApplication.quit()
        overlay.restart_requested.connect(restart_app)

        llm_available = False
        def _check_llm_availability():
            nonlocal llm_available
            llm_available = engine.check_availability()
            if not llm_available:
                logger.warning("LLM not available. Starting in degraded mode.")
                window._system_message_signal.emit(
                    i18n.t("status.llm_unavailable", model=config["llm"]["model"])
                )
                deps["state_manager"].save_to_preferences(deps["memory_manager"])
                deps["proactive_engine"].stop_random_timer()
                deps["reminder_checker"].stop()
                deps["event_monitor"].stop()
        threading.Thread(target=_check_llm_availability, daemon=True).start()

        from src.gui.managers.tray_icon import TrayIcon
        from src.gui.styles.styles import get_style_set
        theme = config.get("ui", {}).get("theme", "light")
        window._tray_icon = TrayIcon(window, config, overlay=overlay, i18n=i18n,
                                      menu_style=get_style_set(theme)["overlay_menu"])

        def show_main_window():
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
            window.show()
            window.raise_()
            window.activateWindow()
            QTimer.singleShot(100, window.raise_)
            QTimer.singleShot(100, window.activateWindow)

        def exit_app():
            _graceful_shutdown(deps)
            window._quit_on_close = True
            from PySide6.QtCore import QCoreApplication
            overlay.close()
            window.close()
            QCoreApplication.quit()

        overlay.set_context_menu_callbacks({
            "chat": show_main_window,
            "notes": window.open_notes,
            "reminders": window.open_reminders,
            "memories": window._open_memories,
            "settings": window._open_settings,
            "exit": exit_app,
        })

        def on_overlay_message(user_input: str):
            overlay._bubble_thinking_signal.emit()
            if user_input.startswith("/"):
                window.process_command(user_input)
                overlay._bubble_hide_signal.emit()
            else:
                window.add_user_message(user_input)

                def _do_overlay_chat():
                    try:
                        response = engine.chat(user_input)
                        overlay._bubble_text_signal.emit(response, True)
                        overlay._assistant_response_signal.emit(response)
                        window._assistant_message_signal.emit(response)
                    except Exception as e:
                        logger.error(f"LLM error: {e}")
                        overlay._bubble_text_signal.emit(f"Error: {str(e)}", False)
                        window._system_message_signal.emit(f"[Error: {str(e)}]")

                threading.Thread(target=_do_overlay_chat, daemon=True).start()

        overlay.message_sent.connect(on_overlay_message)

        overlay.double_clicked.connect(show_main_window)
        overlay.start_animation()
        overlay.show()

        privacy = config.setdefault("privacy", {})
        if not privacy.get("consent_asked"):
            from PySide6.QtWidgets import QDialog
            from src.config.config import get_config_path, save_config
            from src.gui.windows.privacy_consent import PrivacyConsentDialog
            consent = PrivacyConsentDialog(i18n=i18n, parent=overlay)
            accepted = consent.exec() == QDialog.Accepted
            privacy["consent_asked"] = True
            privacy["monitor_active_window"] = bool(accepted)
            save_config(config, get_config_path())

        deps["proactive_engine"].handle_trigger("session_start")

    worker = _InitWorker(config)
    worker.finished.connect(_on_init_complete)
    worker.start()

    app.setQuitOnLastWindowClosed(False)
    ret = app.exec()
    worker.wait(1000)
    if _restart_pending:
        import subprocess
        flags = subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen([sys.executable] + sys.argv, creationflags=flags)
    if deps_ref["deps"] is not None:
        _graceful_shutdown(deps_ref["deps"])
    _close_db()
    os._exit(ret)


def run_cli(config):
    from src.system.commands import handle_command
    deps = _initialize(config)
    engine = deps["engine"]
    memory_manager = deps["memory_manager"]
    state_manager = deps["state_manager"]
    event_monitor = deps["event_monitor"]
    reminder_checker = deps["reminder_checker"]
    context_builder = deps["context_builder"]
    proactive_engine = deps["proactive_engine"]
    i18n = deps["i18n"]

    if not _check_ollama(engine, state_manager, memory_manager,
                          proactive_engine, reminder_checker, event_monitor):
        print(f"\n[ERROR] Cannot connect to Ollama at {config['llm']['endpoint']}")
        print(f"[ERROR] Make sure Ollama is running and model '{config['llm']['model']}' is pulled.\n")
        sys.exit(1)

    def on_proactive_comment(comment: str, trigger_type: str):
        print(f"\n[TOMO] {comment}\n> ", end="", flush=True)

    proactive_engine.set_delivery_callback(on_proactive_comment)
    proactive_engine.handle_trigger("session_start")

    def on_reminder(message: str):
        print(f"\n[REMINDER] {message}\n> ", end="", flush=True)

    reminder_checker.set_callback(on_reminder)

    logger.info("Ollama connected. Starting chat...")
    print(f"\n{'='*50}")
    print(f"  {i18n.t('app.title', name=config['personality']['name'])} is ready!")
    print(f"  Model: {config['llm']['model']}")
    print(i18n.t('commands.help_text'))
    print(f"{'='*50}\n")

    try:
        while True:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                msg, continue_loop = handle_command(
                    user_input, memory_manager, config, event_monitor, context_builder, proactive_engine, state_manager, i18n=i18n
                )
                if msg:
                    print(f"\n{msg}\n")
                if not continue_loop:
                    break
                continue

            print()
            response = engine.chat(user_input)
            print(f"{config['personality']['name']}: {response}\n")

    except KeyboardInterrupt:
        print("\n\nGoodbye!")

    state_manager.save_to_preferences(memory_manager)
    proactive_engine.stop_random_timer()
    reminder_checker.stop()
    event_monitor.stop()
    _close_db()


_db_manager = None


def _close_db():
    if _db_manager is not None:
        try:
            _db_manager.commit()
            _db_manager.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="TomoDesk - Desktop Companion")
    parser.add_argument("--gui", action="store_true", help="Launch GUI mode")
    args = parser.parse_args()

    from src.config.logging_config import setup_logging
    from src.config.config import load_config
    setup_logging()
    config = load_config()

    if args.gui:
        run_gui(config)
    else:
        run_cli(config)


if __name__ == "__main__":
    main()
