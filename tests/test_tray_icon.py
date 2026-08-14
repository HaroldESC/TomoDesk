import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY", "") == "" and os.name != "nt",
    reason="GUI tests require a display server",
)




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
