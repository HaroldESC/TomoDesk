import json
import zipfile

import pytest
import yaml
from pathlib import Path

from src.personality.personality_pack import PersonalityPackManager


@pytest.fixture
def packs_dir(tmp_path):
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    manifest = {
        "id": "test_pack",
        "name": "Test Pack",
        "author": "Tester",
        "version": "1.0",
        "format": "personality-pack-v1",
        "min_tomodesk_version": "0.2.0",
        "type": "personality",
    }
    (pack_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    phrases_dir = pack_path / "phrases"
    phrases_dir.mkdir()
    (phrases_dir / "greeting.json").write_text(
        json.dumps({"greeting": ["Hello!", "Hi there!"]}), encoding="utf-8")
    return tmp_path


class TestPersonalityPackManager:
    def test_scan_packs(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        assert "Test Pack" in mgr.list_packs()

    def test_get_phrases(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        mgr.set_active_pack("Test Pack")
        phrases = mgr.get_phrases("greeting")
        assert phrases == ["Hello!", "Hi there!"]

    def test_get_phrases_no_active_pack(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        assert mgr.get_phrases("greeting") is None

    def test_get_phrases_missing_event(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        mgr.set_active_pack("Test Pack")
        assert mgr.get_phrases("nonexistent") is None

    def test_invalid_pack_skipped(self, tmp_path):
        mgr = PersonalityPackManager(str(tmp_path))
        (tmp_path / "bad_pack").mkdir()
        mgr.scan_packs()
        assert mgr.list_packs() == []

    def test_set_active_pack_invalid(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        mgr.set_active_pack("nonexistent")
        assert mgr._active_pack is None

    def test_discover_sounds_none(self, packs_dir):
        mgr = PersonalityPackManager(str(packs_dir))
        mgr.scan_packs()
        mgr.set_active_pack("Test Pack")
        sounds = mgr.discover_sounds("Test Pack")
        assert sounds == []

    def test_zip_pack_json(self, tmp_path):
        zip_path = tmp_path / "zip_pack.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "id": "zip_pack",
                "name": "Zip Pack",
                "format": "personality-pack-v1",
                "type": "personality",
            }))
            zf.writestr("phrases/greeting.json",
                        json.dumps({"greeting": ["Hey!"]}))
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert "Zip Pack" in mgr.list_packs()
        mgr.set_active_pack("Zip Pack")
        assert mgr.get_phrases("greeting") == ["Hey!"]

    def test_legacy_yaml_pack_supported(self, tmp_path):
        pack_path = tmp_path / "legacy"
        pack_path.mkdir()
        (pack_path / "manifest.yaml").write_text(
            yaml.dump({"name": "Legacy Pack", "type": "personality"}),
            encoding="utf-8")
        phrases_dir = pack_path / "phrases"
        phrases_dir.mkdir()
        (phrases_dir / "greeting.yaml").write_text(
            yaml.dump({"greeting": ["Hola"]}), encoding="utf-8")
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert "Legacy Pack" in mgr.list_packs()
        mgr.set_active_pack("Legacy Pack")
        assert mgr.get_phrases("greeting") == ["Hola"]

    def test_unsupported_format_skipped(self, tmp_path):
        pack_path = tmp_path / "future"
        pack_path.mkdir()
        (pack_path / "manifest.json").write_text(json.dumps({
            "id": "future",
            "name": "Future",
            "format": "personality-pack-v2",
        }), encoding="utf-8")
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert mgr.list_packs() == []

    def test_default_pack_loads(self):
        mgr = PersonalityPackManager("data/personality_packs")
        mgr.scan_packs()
        assert "Default" in mgr.list_packs()
        mgr.set_active_pack("Default")
        phrases = mgr.get_phrases("session_start")
        assert isinstance(phrases, list) and len(phrases) > 0

    def test_bundled_and_user_packs_both_listed(self, tmp_path):
        user = tmp_path / "user"
        user.mkdir()
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        bp = bundled / "bundled_pack"
        bp.mkdir()
        (bp / "manifest.json").write_text(json.dumps({
            "name": "bundled_pack", "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")

        up = user / "user_pack"
        up.mkdir()
        (up / "manifest.json").write_text(json.dumps({
            "name": "user_pack", "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")

        mgr = PersonalityPackManager(str(user), bundled_dir=str(bundled))
        mgr.scan_packs()
        assert sorted(mgr.list_packs()) == ["bundled_pack", "user_pack"]

    def test_user_pack_overrides_bundled_same_name(self, tmp_path):
        user = tmp_path / "user"
        user.mkdir()
        bundled = tmp_path / "bundled"
        bundled.mkdir()

        bp = bundled / "mypack"
        bp.mkdir()
        (bp / "manifest.json").write_text(json.dumps({
            "name": "mypack", "format": "personality-pack-v1",
            "type": "personality", "version": "1.0.0",
        }), encoding="utf-8")

        up = user / "mypack"
        up.mkdir()
        (up / "manifest.json").write_text(json.dumps({
            "name": "mypack", "format": "personality-pack-v1",
            "type": "personality", "version": "2.0.0",
        }), encoding="utf-8")
        phrases_dir = up / "phrases"
        phrases_dir.mkdir()
        (phrases_dir / "greeting.json").write_text(
            json.dumps({"greeting": ["User greeting"]}), encoding="utf-8")

        mgr = PersonalityPackManager(str(user), bundled_dir=str(bundled))
        mgr.scan_packs()
        assert mgr.list_packs() == ["mypack"]
        assert mgr.get_pack_info("mypack")["version"] == "2.0.0"
        mgr.set_active_pack("mypack")
        assert mgr.get_phrases("greeting") == ["User greeting"]
