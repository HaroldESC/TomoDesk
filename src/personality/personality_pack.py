import json
import logging
import re
import yaml
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.personality.zip_security import is_safe_zip_member, validate_zip_archive

logger = logging.getLogger(__name__)

PERSONALITY_PACK_FORMAT = "personality-pack-v1"
MANIFEST_NAME = "manifest.json"
LEGACY_MANIFEST_NAME = "manifest.yaml"


def _safe_pack_name(name: str, fallback: str) -> str:
    """Sanitize a pack name, falling back to ``fallback`` when unusable."""
    if not isinstance(name, str):
        return fallback
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if not cleaned:
        return fallback
    return cleaned[:100]


def _read_json(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load {path}: {e}")
        return None


def _read_yaml(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return None


class PersonalityPackManager:
    """Manages loading and activation of personality packs.

    Reads ``manifest.json`` + ``phrases/*.json`` (``personality-pack-v1``),
    keeping a legacy fallback to ``manifest.yaml`` + ``phrases/*.yaml`` for
    packs installed before the JSON migration.
    """

    def __init__(self, packs_dir: str = "data/personality_packs",
                 bundled_dir: Optional[str] = None):
        self.packs_dir = Path(packs_dir)
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        self.bundled_dir = Path(bundled_dir) if bundled_dir else None
        self._packs: Dict[str, dict] = {}
        self._phrases: Dict[str, dict] = {}
        self._active_pack: Optional[str] = None

    def _scan_sources(self) -> List[Path]:
        sources = []
        if self.bundled_dir is not None and self.bundled_dir != self.packs_dir:
            # bundled primero: los packs del usuario ganan por sobreescritura
            sources.append(self.bundled_dir)
        sources.append(self.packs_dir)
        return sources

    def scan_packs(self):
        """Scan packs_dir (y bundled_dir si existe) por ZIP y directorios."""
        self._packs.clear()
        self._phrases.clear()

        for source in self._scan_sources():
            if not source.is_dir():
                continue
            for entry in sorted(source.iterdir()):
                if entry.is_dir():
                    self._load_pack(entry)
                elif entry.suffix.lower() == ".zip":
                    self._load_zip_pack(entry)

        logger.info(f"Loaded {len(self._packs)} personality pack(s)")

    def _load_pack(self, pack_path: Path):
        manifest_path = pack_path / MANIFEST_NAME
        if not manifest_path.exists():
            legacy_path = pack_path / LEGACY_MANIFEST_NAME
            if not legacy_path.exists():
                logger.warning(f"No manifest in {pack_path}")
                return
            manifest = _read_yaml(legacy_path)
        else:
            manifest = _read_json(manifest_path)

        if manifest is None:
            logger.warning(f"Invalid manifest in {pack_path}")
            return
        if not self._valid_format(manifest):
            return

        name = _safe_pack_name(manifest.get("name", pack_path.name), pack_path.name)
        self._packs[name] = {
            "manifest": manifest,
            "path": pack_path,
            "type": manifest.get("type", "personality"),
        }
        self._load_phrases(name, pack_path / "phrases")
        logger.info(f"Loaded pack: {name}")

    def _load_zip_pack(self, zip_path: Path):
        if not validate_zip_archive(zip_path):
            logger.warning(f"Rejected unsafe ZIP pack: {zip_path}")
            return
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if MANIFEST_NAME in names:
                    manifest = json.loads(zf.read(MANIFEST_NAME))
                else:
                    manifest = yaml.safe_load(zf.read(LEGACY_MANIFEST_NAME))
                if not isinstance(manifest, dict):
                    logger.warning(f"Invalid manifest in ZIP pack {zip_path}")
                    return
                if not self._valid_format(manifest):
                    return
                name = _safe_pack_name(manifest.get("name", zip_path.stem), zip_path.stem)

                self._packs[name] = {
                    "manifest": manifest,
                    "path": zip_path,
                    "type": manifest.get("type", "personality"),
                }
                phrase_files = [
                    f for f in names
                    if f.startswith("phrases/") and f.endswith((".json", ".yaml", ".yml"))
                ]
                self._phrases[name] = {}
                for pf in phrase_files:
                    if pf.endswith(".json"):
                        data = json.loads(zf.read(pf))
                    else:
                        data = yaml.safe_load(zf.read(pf))
                    if isinstance(data, dict):
                        self._phrases[name].update(data)
                logger.info(f"Loaded ZIP pack: {name}")
        except Exception as e:
            logger.error(f"Failed to load ZIP pack {zip_path}: {e}")

    @staticmethod
    def _valid_format(manifest: dict) -> bool:
        fmt = manifest.get("format")
        if fmt and fmt != PERSONALITY_PACK_FORMAT:
            logger.warning(
                f"Pack '{manifest.get('name', '?')}' has unsupported format '{fmt}'"
            )
            return False
        return True

    def _load_phrases(self, pack_name: str, phrases_dir: Path):
        if not phrases_dir.exists():
            return
        self._phrases[pack_name] = {}
        for json_file in sorted(phrases_dir.glob("*.json")):
            data = _read_json(json_file)
            if data:
                self._phrases[pack_name].update(data)
        for yaml_file in sorted(phrases_dir.glob("*.yaml")):
            data = _read_yaml(yaml_file)
            if data:
                self._phrases[pack_name].update(data)

    def get_phrases(self, event_type: str) -> Optional[list]:
        if self._active_pack and self._active_pack in self._phrases:
            pack_data = self._phrases[self._active_pack]
            if event_type in pack_data:
                return pack_data[event_type]
        return None

    def set_active_pack(self, pack_name: Optional[str]):
        if pack_name is not None and pack_name not in self._packs:
            logger.warning(f"Pack '{pack_name}' not found. Keeping current.")
            return
        self._active_pack = pack_name
        logger.info(f"Active pack set to: {pack_name or 'default'}")

    def get_pack_info(self, pack_name: str) -> Optional[dict]:
        return self._packs.get(pack_name, {}).get("manifest")

    def list_packs(self) -> List[str]:
        return list(self._packs.keys())

    def discover_sounds(self, pack_name: str) -> List[str]:
        pack = self._packs.get(pack_name)
        if not pack:
            return []
        pack_path = pack["path"]
        if isinstance(pack_path, Path) and pack_path.suffix == ".zip":
            with zipfile.ZipFile(pack_path, "r") as zf:
                return [f for f in zf.namelist()
                        if f.startswith("sounds/") and f.endswith((".wav", ".ogg", ".mp3"))]
        sounds_dir = pack_path / "sounds"
        if sounds_dir.exists():
            return [str(f) for f in sounds_dir.glob("*") if f.suffix in (".wav", ".ogg", ".mp3")]
        return []