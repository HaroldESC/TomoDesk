"""Loader del Sprite Pack en formato ``sprite-pack-v1`` (manifest.json).

Valida el manifest contra el esquema de ``data/sprites/schema.json`` (si existe),
verifica la existencia de los assets y construye :class:`SpritePackData` junto
con la caché de pixmaps por clip.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from src.core.intents import VisualIntent
from src.gui.sprites.sprite_models import AnimationClip, ClipFrame, SpritePackData

logger = logging.getLogger(__name__)

SPRITE_PACK_FORMAT = "sprite-pack-v1"

CLIP_MODES = ("loop", "once", "hold", "ping_pong", "timed")


class SpriteLoadError(Exception):
    pass


class SpriteLoader:
    def __init__(self, config: dict, base_path: str = "data/sprites"):
        self.config = config
        self.base_path = Path(base_path)
        self._schema: Optional[dict] = None

    def load_sprite(self, sprite_name: str,
                    sprite_dir_override: Optional[Path] = None
                    ) -> Tuple[SpritePackData, Dict[str, List[QPixmap]]]:
        sprite_dir = sprite_dir_override or (self.base_path / sprite_name)
        manifest_path = sprite_dir / "manifest.json"

        if not manifest_path.exists():
            raise SpriteLoadError(f"manifest.json not found for '{sprite_name}'")

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise SpriteLoadError(f"Invalid manifest.json for '{sprite_name}': {e}")

        if manifest.get("format", "") != SPRITE_PACK_FORMAT:
            raise SpriteLoadError(
                f"Sprite '{sprite_name}' has unsupported format "
                f"'{manifest.get('format')}' (expected {SPRITE_PACK_FORMAT})"
            )

        errors = self._validate(manifest, sprite_dir)
        if errors:
            raise SpriteLoadError(f"Sprite '{sprite_name}' validation failed: {errors}")

        pack = self._build_pack(manifest)
        frames_cache = self._load_frames(pack, sprite_dir)

        return pack, frames_cache

    def _validate(self, manifest: dict, sprite_dir: Path) -> List[str]:
        errors: List[str] = []
        schema = self._get_schema()

        if schema:
            try:
                import jsonschema
                try:
                    jsonschema.validate(manifest, schema)
                except jsonschema.ValidationError as e:
                    errors.append(str(e))
            except ImportError:
                logger.warning("jsonschema not installed, skipping schema validation")
        else:
            if manifest.get("format") != SPRITE_PACK_FORMAT:
                errors.append(f"format must be '{SPRITE_PACK_FORMAT}'")
            if not manifest.get("id"):
                errors.append("Missing required field: 'id'")
            if not manifest.get("clips"):
                errors.append("Missing required field: 'clips'")
            assets = manifest.get("assets", {})
            for key in ("image_format", "frame_width", "frame_height"):
                if key not in assets:
                    errors.append(f"Missing required field: 'assets.{key}'")

        if VisualIntent.IDLE.value not in manifest.get("intent_map", {}):
            errors.append(f"Missing required intent: '{VisualIntent.IDLE.value}'")

        for clip_name, cfg in manifest.get("clips", {}).items():
            mode = cfg.get("mode", "loop")
            if mode not in CLIP_MODES:
                errors.append(f"Clip '{clip_name}': unknown mode '{mode}'")
            if mode == "timed" and not cfg.get("interval_ms"):
                errors.append(
                    f"Clip '{clip_name}': mode 'timed' requires 'interval_ms'"
                )
            for frame in cfg.get("frames", []):
                fpath = sprite_dir / frame.get("file", "")
                if not fpath.exists():
                    errors.append(
                        f"Clip '{clip_name}': frame '{frame.get('file')}' not found"
                    )
                elif fpath.suffix.lower() != ".png":
                    errors.append(
                        f"Clip '{clip_name}': frame '{frame.get('file')}' must be PNG"
                    )

        return errors

    def _get_schema(self) -> Optional[dict]:
        if self._schema is None:
            schema_path = self.base_path / "schema.json"
            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    self._schema = json.load(f)
            else:
                self._schema = {}
        return self._schema

    def _build_pack(self, manifest: dict) -> SpritePackData:
        clips: Dict[str, AnimationClip] = {}
        for name, cfg in manifest.get("clips", {}).items():
            frames = [
                ClipFrame(file=f.get("file", ""), duration_ms=f.get("duration_ms", 100))
                for f in cfg.get("frames", [])
            ]
            clips[name] = AnimationClip(
                name=name,
                mode=cfg.get("mode", "loop"),
                frames=frames,
                interval_ms=cfg.get("interval_ms", 0),
                return_to=cfg.get("return_to"),
                interruptible=cfg.get("interruptible", True),
                priority=cfg.get("priority", 0),
                transition_in_ms=cfg.get("transition_in_ms", 0),
                transition_out_ms=cfg.get("transition_out_ms", 0),
                overlays=cfg.get("overlays", []),
                variants=cfg.get("variants", {}),
            )

        return SpritePackData(
            id=manifest["id"],
            name=manifest.get("name", manifest["id"]),
            version=manifest.get("version", "1.0.0"),
            assets=manifest.get("assets", {}),
            intent_map=manifest.get("intent_map", {}),
            fallbacks=manifest.get("fallbacks", {}),
            clips=clips,
            transitions=manifest.get("transitions", {}),
        )

    def _load_frames(self, pack: SpritePackData,
                     sprite_dir: Path) -> Dict[str, List[QPixmap]]:
        width = int(pack.assets.get("frame_width", 150))
        height = int(pack.assets.get("frame_height", 150))
        cache: Dict[str, List[QPixmap]] = {}

        for name, clip in pack.clips.items():
            pixmaps: List[QPixmap] = []
            for frame in clip.frames:
                png_path = sprite_dir / frame.file
                if png_path.exists() and png_path.suffix.lower() == ".png":
                    pix = QPixmap(str(png_path))
                    if not pix.isNull():
                        if (pix.width() != width or pix.height() != height) and pix.width() > 0:
                            pix = pix.scaled(width, height,
                                             Qt.KeepAspectRatio,
                                             Qt.SmoothTransformation)
                        pixmaps.append(pix)
            if pixmaps:
                cache[name] = pixmaps

        return cache

    def list_available_sprites(self) -> List[str]:
        sprites = []
        if not self.base_path.exists():
            return sprites
        for child in self.base_path.iterdir():
            if child.is_dir() and (child / "manifest.json").exists():
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
            pack, frames_cache = self.load_sprite(sprite_name)
            clip_name = pack.intent_map.get(VisualIntent.IDLE.value)
            if clip_name:
                idle_frames = frames_cache.get(clip_name)
                if idle_frames:
                    return idle_frames[0]
        except SpriteLoadError as e:
            logger.warning(f"Could not load preview for '{sprite_name}': {e}")
        return None