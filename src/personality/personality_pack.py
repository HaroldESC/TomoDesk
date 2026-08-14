import logging
import re
import yaml
import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.personality.zip_security import is_safe_zip_member, validate_zip_archive

logger = logging.getLogger(__name__)


def _safe_pack_name(name: str, fallback: str) -> str:
    """Sanitize a pack name, falling back to ``fallback`` when unusable."""
    if not isinstance(name, str):
        return fallback
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if not cleaned:
        return fallback
    return cleaned[:100]


class PersonalityPackManager:
    """Manages loading and activation of personality packs."""

    def __init__(self, packs_dir: str = "data/personality_packs"):
        self.packs_dir = Path(packs_dir)
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        self._packs: Dict[str, dict] = {}
        self._phrases: Dict[str, dict] = {}
        self._active_pack: Optional[str] = None

    def scan_packs(self):
        """Scan packs_dir for ZIP files and directories, load manifests."""
        self._packs.clear()
        self._phrases.clear()

        for entry in sorted(self.packs_dir.iterdir()):
            if entry.is_dir():
                self._load_pack(entry)
            elif entry.suffix.lower() == ".zip":
                self._load_zip_pack(entry)

        logger.info(f"Loaded {len(self._packs)} personality pack(s)")

    def _load_pack(self, pack_path: Path):
        manifest_path = pack_path / "manifest.yaml"
        if not manifest_path.exists():
            logger.warning(f"No manifest.yaml in {pack_path}")
            return
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f)
            if not isinstance(manifest, dict):
                logger.warning(f"Invalid manifest in {pack_path}: not a mapping")
                return
            name = _safe_pack_name(manifest.get("name", pack_path.name), pack_path.name)
            self._packs[name] = {
                "manifest": manifest,
                "path": pack_path,
                "type": manifest.get("type", "personality"),
            }
            self._load_phrases(name, pack_path / "phrases")
            logger.info(f"Loaded pack: {name}")
        except Exception as e:
            logger.error(f"Failed to load pack {pack_path}: {e}")

    def _load_zip_pack(self, zip_path: Path):
        if not validate_zip_archive(zip_path):
            logger.warning(f"Rejected unsafe ZIP pack: {zip_path}")
            return
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                manifest_data = zf.read("manifest.yaml")
                manifest = yaml.safe_load(manifest_data)
                if not isinstance(manifest, dict):
                    logger.warning(f"Invalid manifest in ZIP pack {zip_path}: not a mapping")
                    return
                name = _safe_pack_name(manifest.get("name", zip_path.stem), zip_path.stem)

                self._packs[name] = {
                    "manifest": manifest,
                    "path": zip_path,
                    "type": manifest.get("type", "personality"),
                }
                phrases_dir = "phrases/"
                phrase_files = [f for f in zf.namelist() if f.startswith(phrases_dir) and f.endswith((".yaml", ".yml"))]
                self._phrases[name] = {}
                for pf in phrase_files:
                    data = yaml.safe_load(zf.read(pf))
                    if isinstance(data, dict):
                        self._phrases[name].update(data)
                logger.info(f"Loaded ZIP pack: {name}")
        except Exception as e:
            logger.error(f"Failed to load ZIP pack {zip_path}: {e}")

    def _load_phrases(self, pack_name: str, phrases_dir: Path):
        if not phrases_dir.exists():
            return
        self._phrases[pack_name] = {}
        for yaml_file in phrases_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._phrases[pack_name].update(data)
            except Exception as e:
                logger.warning(f"Failed to load {yaml_file}: {e}")

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
