import pytest
import yaml
from pathlib import Path

from src.personality.personality_pack import PersonalityPackManager


@pytest.fixture
def packs_dir(tmp_path):
    pack_path = tmp_path / "test_pack"
    pack_path.mkdir()
    manifest = {"name": "Test Pack", "author": "Tester", "version": "1.0",
                "min_tomodesk_version": "0.2.0", "type": "personality"}
    (pack_path / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")
    phrases_dir = pack_path / "phrases"
    phrases_dir.mkdir()
    (phrases_dir / "greeting.yaml").write_text(
        yaml.dump({"greeting": ["Hello!", "Hi there!"]}), encoding="utf-8")
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
