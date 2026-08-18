import json
import zipfile

import pytest

from src.context.context_pack import ContextPackManager
from src.core.intents import VisualIntent


def _write_pack(packs_dir, pack_id, events, extra=None):
    pack_dir = packs_dir / pack_id
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": pack_id,
        "name": pack_id.title(),
        "version": "1.0.0",
        "format": "context-pack-v1",
        "events": events,
    }
    if extra:
        manifest.update(extra)
    with open(pack_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f)


def _make_zip(packs_dir, pack_id, events):
    zip_path = packs_dir / f"{pack_id}.zip"
    manifest = {
        "id": pack_id,
        "name": pack_id.title(),
        "version": "1.0.0",
        "format": "context-pack-v1",
        "events": events,
    }
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
    return zip_path


def _config(*active):
    return {"context": {"active_packs": list(active)}}


def test_scan_and_list_packs(tmp_path):
    _write_pack(tmp_path, "vscode", {"build.success": {"intent": "CELEBRATE"}})
    _write_pack(tmp_path, "spotify", {"music.detected": {"intent": "LISTENING"}})
    mgr = ContextPackManager(_config("vscode", "spotify"), str(tmp_path))

    packs = mgr.list_packs()
    assert [p["id"] for p in packs] == ["spotify", "vscode"]
    assert all(p["active"] for p in packs)


def test_resolve_event_match_app(tmp_path):
    _write_pack(tmp_path, "vscode", {
        "app.foreground": {
            "match": {"app": ["code", "visual studio", "terminal"]},
            "intent": "WORKING_CODE",
            "priority": 2,
        }
    })
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))

    req = mgr.resolve_event("app.foreground", {"app": "Visual Studio Code - main.py"})
    assert req is not None
    assert req.intent == VisualIntent.WORKING_CODE
    assert req.priority == 2
    assert req.source == "context:vscode"
    assert not req.one_shot


def test_resolve_event_no_match(tmp_path):
    _write_pack(tmp_path, "vscode", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "WORKING_CODE",
        }
    })
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))
    assert mgr.resolve_event("app.foreground", {"app": "Discord"}) is None


def test_resolve_event_without_match_applies(tmp_path):
    _write_pack(tmp_path, "vscode", {
        "build.success": {"intent": "CELEBRATE", "priority": 3, "one_shot": True}
    })
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))
    req = mgr.resolve_event("build.success", {})
    assert req is not None
    assert req.intent == VisualIntent.CELEBRATE
    assert req.one_shot


def test_inactive_pack_is_ignored(tmp_path):
    _write_pack(tmp_path, "vscode", {
        "build.success": {"intent": "CELEBRATE"}
    })
    mgr = ContextPackManager(_config(), str(tmp_path))
    assert mgr.resolve_event("build.success", {}) is None


def test_priority_wins_across_packs(tmp_path):
    _write_pack(tmp_path, "low", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "WORKING_CODE",
            "priority": 1,
        }
    })
    _write_pack(tmp_path, "high", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "NOTIFICATION",
            "priority": 3,
        }
    })
    mgr = ContextPackManager(_config("low", "high"), str(tmp_path))
    req = mgr.resolve_event("app.foreground", {"app": "Code"})
    assert req is not None
    assert req.intent == VisualIntent.NOTIFICATION
    assert req.source == "context:high"


def test_unknown_intent_is_ignored(tmp_path):
    _write_pack(tmp_path, "vscode", {
        "mystery.event": {"intent": "NOT_AN_OFFICIAL_INTENT"}
    })
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))
    assert mgr.resolve_event("mystery.event", {}) is None


def test_invalid_format_pack_is_ignored(tmp_path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    with open(bad_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({"id": "bad", "format": "other-v1", "events": {}}, f)

    _write_pack(tmp_path, "good", {"build.success": {"intent": "CELEBRATE"}})
    mgr = ContextPackManager(_config("good"), str(tmp_path))
    ids = [p["id"] for p in mgr.list_packs()]
    assert ids == ["good"]


def test_zip_pack_loaded(tmp_path):
    _make_zip(tmp_path, "vscode", {
        "app.foreground": {
            "match": {"app": ["code"]},
            "intent": "WORKING_CODE",
        }
    })
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))
    assert [p["id"] for p in mgr.list_packs()] == ["vscode"]
    req = mgr.resolve_event("app.foreground", {"app": "Visual Studio Code"})
    assert req is not None
    assert req.intent == VisualIntent.WORKING_CODE


def test_unsafe_zip_rejected(tmp_path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../escape.json", "{}")
        zf.writestr("manifest.json", json.dumps({
            "id": "evil", "format": "context-pack-v1", "events": {}
        }))
    mgr = ContextPackManager(_config("evil"), str(tmp_path))
    assert mgr.list_packs() == []


def test_set_active_packs_updates_config(tmp_path):
    _write_pack(tmp_path, "vscode", {"build.success": {"intent": "CELEBRATE"}})
    _write_pack(tmp_path, "spotify", {"music.detected": {"intent": "LISTENING"}})
    cfg = _config("vscode")
    mgr = ContextPackManager(cfg, str(tmp_path))

    mgr.set_active_packs(["spotify"])
    assert cfg["context"]["active_packs"] == ["spotify"]
    assert mgr.resolve_event("build.success", {}) is None
    assert mgr.resolve_event("music.detected", {}) is not None

    mgr.set_active_packs(["nonexistent", "vscode"])
    assert cfg["context"]["active_packs"] == ["vscode"]


def test_scan_packs_after_drop(tmp_path):
    _write_pack(tmp_path, "vscode", {"build.success": {"intent": "CELEBRATE"}})
    mgr = ContextPackManager(_config("vscode"), str(tmp_path))
    assert len(mgr.list_packs()) == 1

    (tmp_path / "vscode" / "manifest.json").unlink()
    mgr.scan_packs()
    assert mgr.list_packs() == []
    assert mgr.resolve_event("build.success", {}) is None
