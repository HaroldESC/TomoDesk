import json
from pathlib import Path

from main import _init_pack_manager


def _make_pack(directory, folder, name):
    pack_path = Path(directory) / folder
    pack_path.mkdir(parents=True, exist_ok=True)
    (pack_path / "manifest.json").write_text(json.dumps({
        "name": name,
        "format": "personality-pack-v1",
        "type": "personality",
    }), encoding="utf-8")


def _config(tmp_path, active=None, enabled=True):
    return {
        "personality": {"name": "Tomo"},
        "personality_packs": {
            "enabled": enabled,
            "active_pack": active,
            "directory": str(tmp_path),
        },
    }


class TestInitPackManager:
    def test_name_normalized_from_active_pack(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Lin"
        assert cfg["personality"]["name"] == "Lin"

    def test_legacy_folder_ref_normalized(self, tmp_path):
        _make_pack(tmp_path, "default", "Tomo")
        cfg = _config(tmp_path, active="Default")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Tomo"
        assert cfg["personality"]["name"] == "Tomo"

    def test_disabled_pack_keeps_manual_name(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin", enabled=False)
        pm = _init_pack_manager(cfg)
        assert pm._active_pack is None
        assert cfg["personality"]["name"] == "Tomo"