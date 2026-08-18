import json
import os

import pytest
from PySide6.QtGui import QImage, QPixmap

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from src.core.intents import VisualIntent
from src.gui.sprites.sprite_loader import SpriteLoader, SpriteLoadError
from src.gui.sprites.sprite_models import SpritePackData


def _write_png(path, width=64, height=64):
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    img.save(str(path))


def _base_manifest():
    return {
        "id": "test_sprite",
        "name": "Test Sprite",
        "version": "1.0.0",
        "format": "sprite-pack-v1",
        "assets": {
            "image_format": "png",
            "frame_width": 64,
            "frame_height": 64,
        },
        "intent_map": {
            "IDLE": "idle",
            "TALKING": "talking",
        },
        "fallbacks": {},
        "clips": {
            "idle": {
                "mode": "loop",
                "frames": [{"file": "idle.png", "duration_ms": 500}],
            },
            "talking": {
                "mode": "loop",
                "frames": [{"file": "talk.png", "duration_ms": 100}],
            },
        },
    }


def _write_sprite(tmp_path, manifest):
    sprite_dir = tmp_path / manifest["id"]
    sprite_dir.mkdir()
    for clip_cfg in manifest["clips"].values():
        for frame in clip_cfg["frames"]:
            _write_png(sprite_dir / frame["file"])
    with open(sprite_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return sprite_dir


class TestSpriteLoader:
    def test_load_missing_manifest_raises(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="manifest.json not found"):
            loader.load_sprite("nonexistent")

    def test_invalid_json_raises(self, tmp_path):
        sprite_dir = tmp_path / "bad_sprite"
        sprite_dir.mkdir()
        with open(sprite_dir / "manifest.json", "w", encoding="utf-8") as f:
            f.write("not valid json")
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="Invalid manifest.json"):
            loader.load_sprite("bad_sprite")

    def test_wrong_format_raises(self, tmp_path):
        manifest = _base_manifest()
        manifest["format"] = "sprite-pack-old"
        sprite_dir = _write_sprite(tmp_path, manifest)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="unsupported format"):
            loader.load_sprite("test_sprite")

    def test_load_sprite_returns_pack_and_frames(self, tmp_path):
        _write_sprite(tmp_path, _base_manifest())
        loader = SpriteLoader({}, str(tmp_path))
        pack, frames = loader.load_sprite("test_sprite")
        assert isinstance(pack, SpritePackData)
        assert pack.id == "test_sprite"
        assert pack.name == "Test Sprite"
        assert "idle" in frames
        assert "talking" in frames
        assert isinstance(frames["idle"][0], QPixmap)

    def test_missing_idle_intent_raises(self, tmp_path):
        manifest = _base_manifest()
        del manifest["intent_map"]["IDLE"]
        _write_sprite(tmp_path, manifest)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="Missing required intent"):
            loader.load_sprite("test_sprite")

    def test_missing_frame_file_raises(self, tmp_path):
        sprite_dir = _write_sprite(tmp_path, _base_manifest())
        manifest = _base_manifest()
        manifest["clips"]["idle"]["frames"][0]["file"] = "missing.png"
        with open(sprite_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="frame 'missing.png' not found"):
            loader.load_sprite("test_sprite")

    def test_timed_mode_requires_interval(self, tmp_path):
        manifest = _base_manifest()
        manifest["clips"]["blink"] = {
            "mode": "timed",
            "frames": [{"file": "idle.png", "duration_ms": 100}],
        }
        _write_sprite(tmp_path, manifest)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="requires 'interval_ms'"):
            loader.load_sprite("test_sprite")

    def test_unknown_mode_raises(self, tmp_path):
        manifest = _base_manifest()
        manifest["clips"]["idle"]["mode"] = "bounce"
        _write_sprite(tmp_path, manifest)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="unknown mode"):
            loader.load_sprite("test_sprite")

    def test_validation_without_jsonschema(self, tmp_path, monkeypatch):
        import src.gui.sprites.sprite_loader as sl
        monkeypatch.setattr("src.gui.sprites.sprite_loader.jsonschema", None, raising=False)
        _write_sprite(tmp_path, _base_manifest())
        loader = SpriteLoader({}, str(tmp_path))
        pack, frames = loader.load_sprite("test_sprite")
        assert pack.id == "test_sprite"
        assert "idle" in frames

    def test_list_available_sprites(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        assert loader.list_available_sprites() == []
        _write_sprite(tmp_path, _base_manifest())
        assert loader.list_available_sprites() == ["test_sprite"]

    def test_get_active_sprite_name_default(self):
        loader = SpriteLoader({"ui": {"sprite": {}}}, "data/sprites")
        assert loader.get_active_sprite_name() == "default"

    def test_get_active_sprite_name_custom(self):
        config = {"ui": {"sprite": {"use_custom": True, "custom_path": "data/sprites/my_custom"}}}
        loader = SpriteLoader(config, "data/sprites")
        assert loader.get_active_sprite_name() == "my_custom"

    def test_get_active_sprite_name_explicit(self):
        loader = SpriteLoader({"ui": {"sprite": {"active": "my_sprite"}}}, "data/sprites")
        assert loader.get_active_sprite_name() == "my_sprite"

    def test_get_preview_none_for_missing(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        assert loader.get_preview("nonexistent") is None

    def test_get_preview_returns_idle_frame(self, tmp_path):
        _write_sprite(tmp_path, _base_manifest())
        loader = SpriteLoader({}, str(tmp_path))
        preview = loader.get_preview("test_sprite")
        assert isinstance(preview, QPixmap)
        assert not preview.isNull()