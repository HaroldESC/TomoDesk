from src.system.commands import cmd_debug


def test_debug_on(mock_i18n, mocker):
    mocker.patch("src.system.commands.save_config")
    config = {}

    msg, continue_loop = cmd_debug("on", None, config, i18n=mock_i18n)

    assert continue_loop is True
    assert config["logs"]["debug_prompts"] is True
    assert "commands.debug_on" in msg


def test_debug_off(mock_i18n, mocker):
    mocker.patch("src.system.commands.save_config")
    config = {"logs": {"debug_prompts": True}}

    msg, continue_loop = cmd_debug("off", None, config, i18n=mock_i18n)

    assert continue_loop is True
    assert config["logs"]["debug_prompts"] is False
    assert "commands.debug_off" in msg


def test_debug_toggle_no_args(mock_i18n, mocker):
    mocker.patch("src.system.commands.save_config")
    config = {}

    _, continue_loop = cmd_debug("", None, config, i18n=mock_i18n)
    assert config["logs"]["debug_prompts"] is True

    _, continue_loop = cmd_debug("", None, config, i18n=mock_i18n)
    assert config["logs"]["debug_prompts"] is False


def test_debug_usage(mock_i18n):
    msg, continue_loop = cmd_debug("bogus", None, {}, i18n=mock_i18n)
    assert continue_loop is True
    assert "commands.debug_usage" in msg


def test_debug_saves_config(mock_i18n, mocker):
    save_config = mocker.patch("src.system.commands.save_config")
    config = {"logs": {}}

    cmd_debug("on", None, config, i18n=mock_i18n)

    save_config.assert_called_once_with(config)