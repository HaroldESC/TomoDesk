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

from src.core.intents import VisualIntent
from src.gui.sprites.sprite_manager import SpriteManager


def _config(size=150):
    return {
        "personality": {"name": "Tomo"},
        "ui": {"character_size": size}
    }


def test_sprite_manager_creation(qapp, tmp_path):
    sm = SpriteManager(_config(), str(tmp_path))
    assert sm.character_size == 150
    assert sm.animation_controller is not None
    pixmap = sm.get_current_pixmap()
    assert not pixmap.isNull()


def test_initial_state_on_error(qapp, tmp_path):
    sm = SpriteManager(_config(100), str(tmp_path))
    assert sm.current_state == "error"


def test_set_state_on_error(qapp, tmp_path):
    sm = SpriteManager(_config(100), str(tmp_path))
    sm.set_state(VisualIntent.TALKING)
    assert sm.current_state == "error"
    assert sm.current_frame == 0


def test_get_current_pixmap(qapp, tmp_path):
    sm = SpriteManager(_config(100), str(tmp_path))
    pixmap = sm.get_current_pixmap()
    assert isinstance(pixmap, QPixmap)
    assert not pixmap.isNull()
    assert pixmap.width() == 100
    assert pixmap.height() == 100


def test_stop_start_animation(qapp, tmp_path):
    sm = SpriteManager(_config(100), str(tmp_path))
    assert not sm.is_animating()
    sm.start_animation()
    assert sm.is_animating()
    sm.stop_animation()
    assert not sm.is_animating()
    sm.start_animation()
    assert sm.is_animating()


def _write_context_pack(packs_dir, pack_id, events):
    import json
    pack_dir = packs_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    with open(pack_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "id": pack_id,
            "name": pack_id,
            "version": "1.0.0",
            "format": "context-pack-v1",
            "events": events,
        }, f)


def _resolver(packs_dir, *active):
    from src.context.context_pack import ContextPackManager
    from src.core.visual_state_resolver import VisualStateResolver
    cfg = {"context": {"active_packs": list(active)}}
    return VisualStateResolver(ContextPackManager(cfg, str(packs_dir)))


def test_set_state_routes_agent_intent_through_resolver(qapp, tmp_path):
    sm = SpriteManager(_config(100), "data/sprites", resolver=_resolver(tmp_path))
    sm.set_state(VisualIntent.TALKING)
    sm._sync_from_resolver()
    assert sm.current_state == "TALKING"

    sm.set_state(VisualIntent.IDLE)
    sm._sync_from_resolver()
    assert sm.current_state == "IDLE"


def test_push_event_sets_context_base_intent(qapp, tmp_path):
    packs_dir = tmp_path / "context"
    _write_context_pack(packs_dir, "vscode", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "WORKING_CODE",
            "priority": 2,
        }
    })
    resolver = _resolver(packs_dir, "vscode")
    sm = SpriteManager(_config(100), "data/sprites", resolver=resolver)

    sm.push_event("app.foreground", {"app": "Visual Studio Code"})
    sm._sync_from_resolver()
    assert sm.resolver.resolve() == VisualIntent.WORKING_CODE
    assert sm.animation_controller.current_clip_name == "idle"

    sm.set_state(VisualIntent.TALKING)
    sm._sync_from_resolver()
    assert sm.current_state == "TALKING"

    sm.set_state(VisualIntent.IDLE)
    sm._sync_from_resolver()
    assert sm.current_state == "WORKING_CODE"


def test_push_event_clears_context_base(qapp, tmp_path):
    packs_dir = tmp_path / "context"
    _write_context_pack(packs_dir, "vscode", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "WORKING_CODE",
            "priority": 2,
        }
    })
    resolver = _resolver(packs_dir, "vscode")
    sm = SpriteManager(_config(100), "data/sprites", resolver=resolver)

    sm.push_event("app.foreground", {"app": "Visual Studio Code"})
    sm._sync_from_resolver()
    assert sm.resolver.resolve() == VisualIntent.WORKING_CODE

    sm.push_event("app.foreground", {"app": "Discord"})
    sm._sync_from_resolver()
    assert sm.resolver.resolve() == VisualIntent.IDLE