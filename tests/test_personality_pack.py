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
        assert "Tomo" in mgr.list_packs()
        mgr.set_active_pack("Tomo")
        phrases = mgr.get_phrases("session_start")
        assert isinstance(phrases, list) and len(phrases) > 0
        assert mgr._active_pack == "Tomo"

    def test_legacy_folder_ref_resolves_to_manifest_name(self):
        mgr = PersonalityPackManager("data/personality_packs")
        mgr.scan_packs()
        mgr.set_active_pack("Default")
        assert mgr._active_pack == "Tomo"

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

    def test_directory_pointing_to_pack_folder_scans_parent(self, tmp_path):
        first = tmp_path / "first_pack"
        first.mkdir()
        (first / "manifest.json").write_text(json.dumps({
            "name": "first_pack", "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")
        phrases_dir = first / "phrases"
        phrases_dir.mkdir()
        (phrases_dir / "greeting.json").write_text(
            json.dumps({"greeting": ["First"]}), encoding="utf-8")

        sibling = tmp_path / "sibling_pack"
        sibling.mkdir()
        (sibling / "manifest.json").write_text(json.dumps({
            "name": "sibling_pack", "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")

        mgr = PersonalityPackManager(str(first))
        mgr.scan_packs()
        assert sorted(mgr.list_packs()) == ["first_pack", "sibling_pack"]
        mgr.set_active_pack("first_pack")
        assert mgr.get_phrases("greeting") == ["First"]

    def test_directory_pointing_to_pack_folder_legacy_manifest(self, tmp_path):
        pack = tmp_path / "legacy_pack"
        pack.mkdir()
        (pack / "manifest.yaml").write_text(
            yaml.dump({"name": "legacy_pack", "type": "personality"}),
            encoding="utf-8")
        phrases_dir = pack / "phrases"
        phrases_dir.mkdir()
        (phrases_dir / "greeting.yaml").write_text(
            yaml.dump({"greeting": ["Hola"]}), encoding="utf-8")

        mgr = PersonalityPackManager(str(pack))
        mgr.scan_packs()
        assert "legacy_pack" in mgr.list_packs()
        mgr.set_active_pack("legacy_pack")
        assert mgr.get_phrases("greeting") == ["Hola"]


class TestPackNameResolution:
    def _make(self, tmp_path, folder, manifest):
        pack_path = tmp_path / folder
        pack_path.mkdir()
        (pack_path / "manifest.json").write_text(json.dumps({
            "id": manifest.get("id", folder),
            "name": manifest.get("name", folder),
            "format": "personality-pack-v1",
            "type": "personality",
        }), encoding="utf-8")

    def test_resolve_by_manifest_name(self, tmp_path):
        self._make(tmp_path, "folder_a", {"name": "Alice", "id": "alice"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert mgr.resolve_pack("Alice") == "Alice"

    def test_resolve_by_folder_name_case_insensitive(self, tmp_path):
        self._make(tmp_path, "folder_b", {"name": "Bob", "id": "bob"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert mgr.resolve_pack("folder_b") == "Bob"
        assert mgr.resolve_pack("FOLDER_B") == "Bob"

    def test_resolve_by_id(self, tmp_path):
        self._make(tmp_path, "folder_c", {"name": "Carol", "id": "carol-id"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert mgr.resolve_pack("carol-id") == "Carol"

    def test_resolve_unknown_returns_none(self, tmp_path):
        self._make(tmp_path, "folder_d", {"name": "Dave", "id": "dave"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        assert mgr.resolve_pack("nobody") is None

    def test_get_character_name_falls_back_to_folder(self, tmp_path):
        self._make(tmp_path, "folder_e", {"name": "", "id": "e"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        key = mgr.resolve_pack("folder_e")
        assert key is not None
        assert mgr.get_character_name(key) == "folder_e"

    def test_set_active_pack_matches_folder_name(self, tmp_path):
        self._make(tmp_path, "folder_f", {"name": "Fran", "id": "fran"})
        mgr = PersonalityPackManager(str(tmp_path))
        mgr.scan_packs()
        mgr.set_active_pack("folder_f")
        assert mgr._active_pack == "Fran"
