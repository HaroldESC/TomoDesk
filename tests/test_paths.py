import sys
from pathlib import Path

import pytest

import src.config.paths as paths


class TestDevMode:
    def test_dev_dirs_all_map_to_project_root(self):
        root = paths._project_root()
        assert paths.resource_dir() == root
        assert paths.user_data_dir() == root
        assert paths.user_config_dir() == root
        assert paths.default_config_path() == root / "config.yaml"
        assert paths.log_dir() == root / "data"
        assert paths.default_sprite_dir() == root / "data" / "sprites"

    def test_not_frozen(self):
        assert paths.is_frozen() is False

    def test_bundled_defaults_none_in_dev(self):
        assert paths.bundled_defaults_dir("data", "personality_packs") is None


class TestResolve:
    def test_relative_user_key_resolves_under_user_data(self):
        cfg = {"database": {"sqlite_path": "data/custom.db"}}
        assert (paths.resolve(cfg, "database", "sqlite_path")
                == paths.user_data_dir() / "data" / "custom.db")

    def test_relative_resource_key_resolves_under_resource(self):
        cfg = {"paths": {"locales": "locales"}}
        assert (paths.resolve(cfg, "paths", "locales")
                == paths.resource_dir() / "locales")

    def test_missing_key_uses_default(self):
        assert (paths.resolve({}, "database", "sqlite_path")
                == paths.user_data_dir() / "data" / "tomodesk.db")

    def test_empty_value_uses_default(self):
        cfg = {"memory": {"chroma_persist_path": ""}}
        assert (paths.resolve(cfg, "memory", "chroma_persist_path")
                == paths.user_data_dir() / "chroma_db")

    def test_absolute_passthrough(self):
        abs_path = (
            Path("C:/x/sqlite.db") if sys.platform == "win32"
            else Path("/tmp/sqlite.db")
        )
        cfg = {"database": {"sqlite_path": str(abs_path)}}
        assert paths.resolve(cfg, "database", "sqlite_path") == abs_path

    def test_nested_config_key(self):
        cfg = {"ui": {"sprite": {"custom_path": "my/sprite"}}}
        assert (paths.resolve(cfg, "ui", "sprite", "custom_path")
                == paths.user_data_dir() / "my" / "sprite")

    def test_resolve_raw_relative(self):
        base = Path("/base")
        assert paths.resolve_raw("rel/sub", base) == base / "rel" / "sub"

    def test_resolve_raw_absolute(self):
        base = Path("/base")
        abs_path = (
            Path("C:/abs/x") if sys.platform == "win32" else Path("/abs/x")
        )
        assert paths.resolve_raw(str(abs_path), base) == abs_path

    def test_resolve_raw_empty(self):
        assert paths.resolve_raw("", Path("/base")) == Path("/base")

    def test_user_resolve_anchors_to_user_data(self):
        assert (paths.user_resolve("data/context_packs")
                == paths.user_data_dir() / "data" / "context_packs")


class TestFrozenWindows:
    @pytest.fixture
    def frozen_win(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"),
                            raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        (tmp_path / "bundle").mkdir()
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
        monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
        return tmp_path

    def test_frozen_dirs(self, frozen_win):
        assert paths.is_frozen() is True
        assert paths.resource_dir() == frozen_win / "bundle"
        assert paths.user_data_dir() == frozen_win / "local" / "TomoDesk"
        assert paths.user_config_dir() == frozen_win / "roaming" / "TomoDesk"
        assert paths.default_config_path() == frozen_win / "roaming" / "TomoDesk" / "config.yaml"
        assert paths.log_dir() == frozen_win / "local" / "TomoDesk" / "data"

    def test_bundled_defaults_dir_in_frozen(self, frozen_win):
        assert (paths.bundled_defaults_dir("data", "packs")
                == frozen_win / "bundle" / "data" / "packs")

    def test_ensure_user_dirs_creates_data_dirs(self, frozen_win):
        paths.ensure_user_dirs()
        assert (frozen_win / "local" / "TomoDesk" / "data").is_dir()
        assert (frozen_win / "local" / "TomoDesk" / "data" / "models").is_dir()


class TestFrozenPosix:
    def test_frozen_dirs_with_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"),
                            raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
        (tmp_path / "bundle").mkdir()

        assert paths.user_data_dir() == tmp_path / "xdg-data" / "tomodesk"
        assert paths.user_config_dir() == tmp_path / "xdg-config" / "tomodesk"
        assert paths.resource_dir() == tmp_path / "bundle"

    def test_frozen_dirs_without_xdg_fallback_home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"),
                            raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home",
                            staticmethod(lambda: tmp_path / "home"))
        (tmp_path / "home").mkdir()
        (tmp_path / "bundle").mkdir()

        assert paths.user_data_dir() == tmp_path / "home" / ".local" / "share" / "tomodesk"
        assert paths.user_config_dir() == tmp_path / "home" / ".config" / "tomodesk"