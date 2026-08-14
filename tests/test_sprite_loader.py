import json
import os

import pytest
from PySide6.QtGui import QPixmap

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from src.gui.sprites.sprite_loader import SpriteLoader, SpriteLoadError


class TestSpriteLoader:
    def test_load_default_procedural(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="sprite.json not found"):
            loader.load_sprite("default")

    def test_load_sprite_missing_raises(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="sprite.json not found"):
            loader.load_sprite("nonexistent")

    def test_load_sprite_with_json(self, tmp_path):
        sprite_dir = tmp_path / "test_sprite"
        sprite_dir.mkdir()
        sprite_json = {
            "name": "test_sprite",
            "frame_width": 64,
            "frame_height": 64,
            "states": {
                "idle": {
                    "type": "simple",
                    "frames": ["idle.png"],
                    "frame_durations": [500],
                },
                "talking": {
                    "type": "simple",
                    "frames": ["talk.png"],
                    "frame_durations": [100],
                },
            },
        }
        with open(sprite_dir / "sprite.json", "w") as f:
            json.dump(sprite_json, f)
        # Create dummy PNGs
        from PySide6.QtGui import QImage
        img = QImage(64, 64, QImage.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        img.save(str(sprite_dir / "idle.png"))
        img.save(str(sprite_dir / "talk.png"))

        loader = SpriteLoader({}, str(tmp_path))
        config, frames = loader.load_sprite("test_sprite")
        assert config["name"] == "test_sprite"
        assert "idle" in frames
        assert "talking" in frames

    def test_invalid_json_raises(self, tmp_path):
        sprite_dir = tmp_path / "bad_sprite"
        sprite_dir.mkdir()
        with open(sprite_dir / "sprite.json", "w") as f:
            f.write("not valid json")
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="Invalid sprite.json"):
            loader.load_sprite("bad_sprite")

    def test_list_available_sprites(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        assert loader.list_available_sprites() == []
        sprite_dir = tmp_path / "my_sprite"
        sprite_dir.mkdir()
        with open(sprite_dir / "sprite.json", "w") as f:
            json.dump({"name": "my_sprite", "states": {"idle": {}, "talking": {}}}, f)
        assert loader.list_available_sprites() == ["my_sprite"]

    def test_get_active_sprite_name_default(self):
        config = {"ui": {"sprite": {}}}
        loader = SpriteLoader(config, "data/sprites")
        assert loader.get_active_sprite_name() == "default"

    def test_get_active_sprite_name_custom(self):
        config = {"ui": {"sprite": {"use_custom": True, "custom_path": "data/sprites/my_custom"}}}
        loader = SpriteLoader(config, "data/sprites")
        assert loader.get_active_sprite_name() == "my_custom"

    def test_get_active_sprite_name_explicit(self):
        config = {"ui": {"sprite": {"active": "my_sprite"}}}
        loader = SpriteLoader(config, "data/sprites")
        assert loader.get_active_sprite_name() == "my_sprite"

    def test_get_preview_none_for_missing(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        preview = loader.get_preview("nonexistent")
        assert preview is None

    def test_get_preview_default_procedural(self, tmp_path):
        loader = SpriteLoader({}, str(tmp_path))
        preview = loader.get_preview("default")
        assert preview is None

    def test_non_default_missing_frame_raises(self, tmp_path):
        sprite_dir = tmp_path / "test_sprite"
        sprite_dir.mkdir()
        sprite_json = {
            "name": "test_sprite",
            "frame_width": 64,
            "frame_height": 64,
            "states": {
                "idle": {
                    "type": "simple",
                    "frames": ["missing.png"],
                    "frame_durations": [500],
                },
                "talking": {
                    "type": "simple",
                    "frames": ["talk.png"],
                    "frame_durations": [100],
                },
            },
        }
        with open(sprite_dir / "sprite.json", "w") as f:
            json.dump(sprite_json, f)
        loader = SpriteLoader({}, str(tmp_path))
        with pytest.raises(SpriteLoadError, match="frame.*not found"):
            loader.load_sprite("test_sprite")

    def test_sprite_config_without_jsonschema(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.gui.sprites.sprite_loader.jsonschema", None, raising=False)
        # Simulate missing jsonschema by monkeypatching
        import src.gui.sprites.sprite_loader as sl
        original = getattr(sl, 'jsonschema', None)
        # We'll just verify the warning path works
        sprite_dir = tmp_path / "test_sprite"
        sprite_dir.mkdir()
        sprite_json = {
            "name": "test_sprite",
            "frame_width": 64,
            "frame_height": 64,
            "states": {
                "idle": {
                    "type": "simple",
                    "frames": [],
                    "frame_durations": [],
                },
                "talking": {
                    "type": "simple",
                    "frames": [],
                    "frame_durations": [],
                },
            },
        }
        with open(sprite_dir / "sprite.json", "w") as f:
            json.dump(sprite_json, f)
        loader = SpriteLoader({}, str(tmp_path))
        config, frames = loader.load_sprite("test_sprite")
        assert config["name"] == "test_sprite"
