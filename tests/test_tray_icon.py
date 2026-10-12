import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY", "") == "" and os.name != "nt",
    reason="GUI tests require a display server",
)




def test_tray_icon_painted_with_design_tokens(qapp, monkeypatch):
    """Design.md §5.1: el icono usa ACCENT y TEXT_ON_ACCENT, no hex sueltos."""
    from PySide6.QtGui import QColor

    from src.gui.managers.tray_icon import TrayIcon
    from src.gui.styles.styles import ACCENT, TEXT_ON_ACCENT

    painted: list[str] = []
    real_color = QColor

    def spy(*args):
        painted.append(args[0])
        return real_color(*args)

    monkeypatch.setattr("src.gui.managers.tray_icon.QColor", spy)

    main_window = SimpleNamespace(open_notes=lambda: None, open_reminders=lambda: None)
    config = {"personality": {"name": "TestTomo"}}
    i18n = SimpleNamespace(t=lambda key, **kw: key)

    tray = TrayIcon(main_window, config, i18n=i18n)
    try:
        tray._make_icon_pixmap(32)
    finally:
        tray.hide()

    # __init__ pinta el icono varias veces; lo que importa es que SOLO use
    # colores del sistema de diseño.
    assert painted
    assert set(painted) == {ACCENT, TEXT_ON_ACCENT}


def test_tray_icon_creation(qapp, mocker):
    from src.gui.managers.tray_icon import TrayIcon

    main_window = mocker.Mock()
    main_window.open_notes = mocker.Mock()
    main_window.open_reminders = mocker.Mock()
    main_window._update_status_message = mocker.Mock()

    config = {"personality": {"name": "TestTomo"}}
    i18n = mocker.Mock()
    i18n.t = mocker.Mock(side_effect=lambda key, **kw: key)

    tray = TrayIcon(main_window, config, i18n=i18n)
    assert tray is not None
    assert tray.toolTip() == "TomoDesk \u2014 TestTomo"
    tray.hide()


def test_tray_restart_action_emits_signal(qapp, mocker):
    from src.gui.managers.tray_icon import TrayIcon

    main_window = mocker.Mock()
    main_window.open_notes = mocker.Mock()
    main_window.open_reminders = mocker.Mock()
    main_window._update_status_message = mocker.Mock()

    config = {"personality": {"name": "TestTomo"}}
    i18n = mocker.Mock()
    i18n.t = mocker.Mock(side_effect=lambda key, **kw: key)

    tray = TrayIcon(main_window, config, i18n=i18n)
    try:
        menu = tray.contextMenu()
        assert menu is not None

        restart_action = next(
            (a for a in menu.actions() if a.text() == "menu.restart"), None
        )
        assert restart_action is not None

        emitted = []
        tray.restart_requested.connect(lambda: emitted.append(True))
        restart_action.trigger()
        assert emitted == [True]
    finally:
        tray.hide()
