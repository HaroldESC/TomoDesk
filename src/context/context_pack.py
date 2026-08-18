"""Gestor de Context Packs (formato ``context-pack-v1``).

Un Context Pack traduce eventos de aplicaciones/sistema a intenciones
visuales (:class:`IntentRequest`). No conoce sprites: produce el "qué",
nunca el "cómo".
"""

import json
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.core.intents import VisualIntent, normalize_intent
from src.core.visual_state_resolver import IntentRequest
from src.personality.zip_security import is_safe_zip_member

logger = logging.getLogger(__name__)

CONTEXT_PACK_FORMAT = "context-pack-v1"

MANIFEST_NAME = "manifest.json"


@dataclass
class ContextPack:
    id: str
    name: str
    version: str
    format: str
    events: Dict[str, dict]
    path: Path
    source: str = "dir"
    app: Optional[str] = None
    active: bool = False


class ContextPackManager:
    """Escanea ``packs_dir`` y resuelve eventos a intenciones visuales."""

    def __init__(self, config: Optional[dict] = None,
                 packs_dir: str = "data/context_packs"):
        self.config = config
        self.packs_dir = Path(packs_dir)
        self._packs: Dict[str, ContextPack] = {}
        self._active_ids: List[str] = []
        self._schema: Optional[dict] = None
        self.scan_packs()

    def scan_packs(self) -> None:
        self._packs.clear()

        if self.packs_dir.exists():
            for entry in sorted(self.packs_dir.iterdir()):
                try:
                    if entry.is_dir():
                        manifest_path = entry / MANIFEST_NAME
                        if manifest_path.is_file():
                            self._load_from_manifest(manifest_path, source="dir")
                    elif entry.suffix.lower() == ".zip":
                        self._load_zip(entry)
                except Exception as e:
                    logger.error(f"Failed to scan context pack '{entry.name}': {e}")

        active = []
        if self.config is not None:
            active = self.config.get("context", {}).get("active_packs", [])
        self._active_ids = [pid for pid in active if pid in self._packs]
        for pid in self._active_ids:
            self._packs[pid].active = True

    def _load_from_manifest(self, manifest_path: Path, source: str) -> None:
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Invalid manifest {manifest_path}: {e}")
            return

        if manifest.get("format", "") != CONTEXT_PACK_FORMAT:
            logger.warning(
                f"Context pack '{manifest.get('id', manifest_path.name)}' "
                f"has unsupported format '{manifest.get('format')}'"
            )
            return

        errors = self._validate(manifest)
        if errors:
            logger.error(
                f"Context pack '{manifest.get('id', manifest_path.name)}' "
                f"validation failed: {errors}"
            )
            return

        pack = ContextPack(
            id=manifest["id"],
            name=manifest.get("name", manifest["id"]),
            version=manifest.get("version", "1.0.0"),
            format=manifest["format"],
            events=manifest.get("events", {}),
            path=manifest_path.parent,
            source=source,
            app=manifest.get("app"),
        )
        self._packs[pack.id] = pack

    def _load_zip(self, zip_path: Path) -> None:
        try:
            if zip_path.stat().st_size > 50 * 1024 * 1024:
                logger.warning(f"Rejected oversized context pack ZIP: {zip_path}")
                return
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if MANIFEST_NAME not in names:
                    logger.warning(f"ZIP missing {MANIFEST_NAME}: {zip_path}")
                    return
                if not all(is_safe_zip_member(n) for n in names):
                    logger.warning(f"ZIP contains unsafe members: {zip_path}")
                    return
                with zf.open(MANIFEST_NAME) as mf:
                    manifest = json.load(mf)
        except (zipfile.BadZipFile, json.JSONDecodeError, OSError) as e:
            logger.error(f"Invalid context pack ZIP {zip_path}: {e}")
            return

        if manifest.get("format", "") != CONTEXT_PACK_FORMAT:
            logger.warning(
                f"Context pack '{manifest.get('id', zip_path.name)}' "
                f"has unsupported format '{manifest.get('format')}'"
            )
            return

        errors = self._validate(manifest)
        if errors:
            logger.error(
                f"Context pack '{manifest.get('id', zip_path.name)}' "
                f"validation failed: {errors}"
            )
            return

        pack = ContextPack(
            id=manifest["id"],
            name=manifest.get("name", manifest["id"]),
            version=manifest.get("version", "1.0.0"),
            format=manifest["format"],
            events=manifest.get("events", {}),
            path=zip_path,
            source="zip",
            app=manifest.get("app"),
        )
        self._packs[pack.id] = pack

    def _validate(self, manifest: dict) -> List[str]:
        errors: List[str] = []
        schema = self._get_schema()

        if schema:
            try:
                import jsonschema
                try:
                    jsonschema.validate(manifest, schema)
                    return errors
                except jsonschema.ValidationError as e:
                    errors.append(str(e))
            except ImportError:
                logger.warning("jsonschema not installed, skipping schema validation")

        if manifest.get("format") != CONTEXT_PACK_FORMAT:
            errors.append(f"format must be '{CONTEXT_PACK_FORMAT}'")
        if not manifest.get("id"):
            errors.append("Missing required field: 'id'")
        for ev_name, cfg in manifest.get("events", {}).items():
            intent = cfg.get("intent")
            if not isinstance(intent, str) or not intent.strip():
                errors.append(f"Event '{ev_name}': missing 'intent'")
        return errors

    def _get_schema(self) -> Optional[dict]:
        if self._schema is None:
            schema_path = self.packs_dir / "schema.json"
            if schema_path.exists():
                try:
                    with open(schema_path, encoding="utf-8") as f:
                        self._schema = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._schema = {}
            else:
                self._schema = {}
        return self._schema

    # ── Resolución de eventos ────────────────────────────────────────────

    def resolve_event(self, event: str,
                      payload: Optional[dict] = None) -> Optional[IntentRequest]:
        best: Optional[IntentRequest] = None
        for pack_id in self._active_ids:
            pack = self._packs.get(pack_id)
            if pack is None:
                continue
            cfg = pack.events.get(event)
            if cfg is None:
                continue
            if not self._matches(cfg, payload):
                continue
            intent = normalize_intent(cfg.get("intent"))
            if intent is None:
                continue
            request = IntentRequest(
                intent=intent,
                priority=int(cfg.get("priority", 1)),
                source=f"context:{pack.id}",
                one_shot=bool(cfg.get("one_shot", False)),
            )
            if best is None or request.priority > best.priority:
                best = request
        return best

    def _matches(self, cfg: dict, payload: Optional[dict]) -> bool:
        match = cfg.get("match")
        if not match:
            return True
        app_terms = match.get("app", [])
        if not app_terms:
            return True
        app = str((payload or {}).get("app", "")).lower()
        return any(term.lower() in app for term in app_terms)

    # ── Consulta y configuración ─────────────────────────────────────────

    def list_packs(self) -> List[dict]:
        result = []
        for pack in self._packs.values():
            result.append({
                "id": pack.id,
                "name": pack.name,
                "version": pack.version,
                "app": pack.app,
                "active": pack.id in self._active_ids,
                "source": pack.source,
            })
        return sorted(result, key=lambda p: p["id"])

    def set_active_packs(self, pack_ids: List[str]) -> None:
        known = set(self._packs)
        self._active_ids = [pid for pid in pack_ids if pid in known]
        for pack in self._packs.values():
            pack.active = pack.id in self._active_ids
        if self.config is not None:
            self.config.setdefault("context", {})["active_packs"] = list(self._active_ids)