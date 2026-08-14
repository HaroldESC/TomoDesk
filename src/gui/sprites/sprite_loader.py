import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class SpriteLoadError(Exception):
    pass


class SpriteLoader:
    def __init__(self, config: dict, base_path: str = "data/sprites"):
        self.config = config
        self.base_path = Path(base_path)
        self._schema: Optional[dict] = None

    def load_sprite(self, sprite_name: str,
                    sprite_dir_override: Optional[Path] = None
                    ) -> Tuple[dict, Dict[str, List[QPixmap]]]:
        sprite_dir = sprite_dir_override or (self.base_path / sprite_name)
        sprite_json_path = sprite_dir / "sprite.json"

        if not sprite_json_path.exists():
            raise SpriteLoadError(f"sprite.json not found for '{sprite_name}'")

        try:
            with open(sprite_json_path, encoding="utf-8") as f:
                sprite_config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise SpriteLoadError(f"Invalid sprite.json for '{sprite_name}': {e}")

        errors = self._validate(sprite_config, sprite_dir)
        if errors:
            raise SpriteLoadError(f"Sprite '{sprite_name}' validation failed: {errors}")

        frames_cache = self._load_frames(sprite_config, sprite_dir)

        return sprite_config, frames_cache

    def _validate(self, sprite_config: dict, sprite_dir: Path) -> List[str]:
        errors = []
        schema = self._get_schema()

        try:
            import jsonschema
            try:
                jsonschema.validate(sprite_config, schema)
            except jsonschema.ValidationError as e:
                errors.append(str(e))
        except ImportError:
            logger.warning("jsonschema not installed, skipping schema validation")

        states = sprite_config.get("states", {})
        if "idle" not in states:
            errors.append("Missing required state: 'idle'")
        if "talking" not in states:
            errors.append("Missing required state: 'talking'")

        for state_name, cfg in states.items():
            anim_type = cfg.get("type", "simple")
            if anim_type in ("simple", "one_shot"):
                frames = cfg.get("frames", [])
                durations = cfg.get("frame_durations", [])
                if len(frames) != len(durations):
                    errors.append(
                        f"State '{state_name}': frames ({len(frames)}) "
                        f"must match frame_durations ({len(durations)})"
                    )
                for fname in frames:
                    if not (sprite_dir / fname).exists():
                        errors.append(
                            f"State '{state_name}': frame '{fname}' not found"
                        )

            elif anim_type == "composite":
                for sub in cfg.get("animations", []):
                    sframes = sub.get("frames", [])
                    sdurations = sub.get("frame_durations", [])
                    if len(sframes) != len(sdurations):
                        errors.append(
                            f"State '{state_name}/{sub.get('name')}': "
                            f"frames ({len(sframes)}) must match frame_durations ({len(sdurations)})"
                        )

        for tname, tcfg in sprite_config.get("transitions", {}).items():
            tframes = tcfg.get("frames", [])
            tdurations = tcfg.get("frame_durations", [])
            if len(tframes) != len(tdurations):
                errors.append(
                    f"Transition '{tname}': frames ({len(tframes)}) "
                    f"must match frame_durations ({len(tdurations)})"
                )

        return errors

    def _get_schema(self) -> dict:
        if self._schema is None:
            schema_path = self.base_path / "schema.json"
            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    self._schema = json.load(f)
            else:
                self._schema = {}
        return self._schema

    def _load_frames(self, sprite_config: dict,
                     sprite_dir: Path) -> Dict[str, List[QPixmap]]:
        width = sprite_config.get("frame_width", 150)
        height = sprite_config.get("frame_height", 150)
        cache: Dict[str, List[QPixmap]] = {}

        def _load_pngs(ref: str) -> List[QPixmap]:
            png_path = sprite_dir / ref
            if png_path.exists() and png_path.suffix.lower() == ".png":
                pix = QPixmap(str(png_path))
                if not pix.isNull():
                    if (pix.width() != width or pix.height() != height) and pix.width() > 0:
                        pix = pix.scaled(width, height,
                                         Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)
                    return [pix]
            return []

        states = sprite_config.get("states", {})

        for state_name, cfg in states.items():
            anim_type = cfg.get("type", "simple")
            frames_list = []

            if anim_type == "composite":
                for sub in cfg.get("animations", []):
                    sub_frames = []
                    for fname in sub.get("frames", []):
                        loaded = _load_pngs(fname)
                        if loaded:
                            sub_frames.extend(loaded)
                    if sub_frames:
                        cache[f"{state_name}/{sub['name']}"] = sub_frames
            else:
                for fname in cfg.get("frames", []):
                    loaded = _load_pngs(fname)
                    if loaded:
                        frames_list.extend(loaded)

            if frames_list:
                cache[state_name] = frames_list

        for tname, tcfg in sprite_config.get("transitions", {}).items():
            t_frames = []
            for fname in tcfg.get("frames", []):
                loaded = _load_pngs(fname)
                if loaded:
                    t_frames.extend(loaded)
            if t_frames:
                cache[tname] = t_frames

        return cache

    def list_available_sprites(self) -> List[str]:
        sprites = []
        if not self.base_path.exists():
            return sprites
        for child in self.base_path.iterdir():
            if child.is_dir() and (child / "sprite.json").exists():
                sprites.append(child.name)
        return sorted(sprites)

    def get_active_sprite_name(self) -> str:
        ui_config = self.config.get("ui", {})
        sprite_config = ui_config.get("sprite", {})

        if sprite_config.get("use_custom", False):
            custom_path = sprite_config.get("custom_path", "")
            if custom_path:
                return Path(custom_path).name

        return sprite_config.get("active", "default")

    def get_preview(self, sprite_name: str) -> Optional[QPixmap]:
        try:
            sprite_config, frames_cache = self.load_sprite(sprite_name)
            idle_frames = frames_cache.get("idle") or frames_cache.get("idle/blink", [])
            if idle_frames:
                return idle_frames[0]
        except SpriteLoadError as e:
            logger.warning(f"Could not load preview for '{sprite_name}': {e}")
        return None
