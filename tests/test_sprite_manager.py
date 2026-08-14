import os

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from PySide6.QtGui import QPixmap

from src.gui.sprites.sprite_manager import SpriteManager
from src.gui.sprites.animation_manager import AnimationState


def test_sprite_manager_creation(qapp, tmp_path):
    config = {
        "personality": {"name": "Tomo"},
        "ui": {"character_size": 150}
    }
    sm = SpriteManager(config, str(tmp_path))
    assert sm.character_size == 150
    assert sm.animation_manager is not None
    pixmap = sm.get_current_pixmap()
    assert not pixmap.isNull()


def test_initial_state_on_error(qapp, tmp_path):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 100}}
    sm = SpriteManager(config, str(tmp_path))
    assert sm.current_state == "error"


def test_set_state_on_error(qapp, tmp_path):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 100}}
    sm = SpriteManager(config, str(tmp_path))
    sm.set_state(AnimationState.TALKING)
    assert sm.current_state == "error"
    assert sm.current_frame == 0


def test_get_current_pixmap(qapp, tmp_path):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 100}}
    sm = SpriteManager(config, str(tmp_path))
    pixmap = sm.get_current_pixmap()
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 100
    assert pixmap.height() == 100


def test_stop_start_animation(qapp, tmp_path):
    config = {"personality": {"name": "Tomo"}, "ui": {"character_size": 100}}
    sm = SpriteManager(config, str(tmp_path))
    assert not sm.is_animating()
    sm.start_animation()
    assert sm.is_animating()
    sm.stop_animation()
    assert not sm.is_animating()
    sm.start_animation()
    assert sm.is_animating()
