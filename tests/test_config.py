import yaml
import pytest

from src.config.config import load_config, save_config, validate_llm_endpoint


class TestValidateLlmEndpoint:
    def test_valid_endpoints(self):
        valid = [
            "https://api.groq.com/openai",
            "http://localhost:11434",
            "https://127.0.0.1:8080/v1",
        ]
        for url in valid:
            assert validate_llm_endpoint(url) is True, url

    def test_invalid_endpoints(self):
        invalid = [
            "",
            None,
            "not-a-url",
            "ftp://example.com",
            "http://",
            "https://",
            "javascript:alert(1)",
            "file:///etc/passwd",
        ]
        for url in invalid:
            assert validate_llm_endpoint(url) is False, url


class TestSaveConfig:
    def test_save_config_strips_api_key(self, tmp_path):
        config = {
            "llm": {"model": "qwen", "api_key": "sk-super-secret"},
            "memory": {"max_short_term_messages": 20},
        }
        path = tmp_path / "c.yaml"
        save_config(config, path)
        assert path.exists()
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "api_key" not in loaded["llm"]
        assert loaded["llm"]["model"] == "qwen"


class TestLoadConfig:
    def test_load_config_with_required_keys(self, tmp_path):
        config = {
            "llm": {"model": "qwen"},
            "memory": {"max_short_term_messages": 20},
            "personality": {"pack": "tomo"},
            "modes": {"proactive": True},
            "database": {"path": "data/tomodesk.db"},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        loaded = load_config(path)
        for key in ("llm", "memory", "personality", "modes", "database"):
            assert key in loaded

    def test_load_config_fills_missing_nested_defaults(self, tmp_path):
        config = {
            "llm": {"model": "qwen"},
            "memory": {"max_short_term_messages": 20},
            "personality": {"pack": "tomo"},
            "modes": {"proactive": True},
            "database": {},
        }
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        loaded = load_config(path)
        assert loaded["database"]["sqlite_path"] == "./data/tomodesk.db"
        assert loaded["memory"]["chroma_persist_path"] == "./chroma_db"
        assert loaded["memory"]["embedding_model"] == "all-MiniLM-L6-v2"
        assert loaded["llm"]["provider"] == "ollama"
        assert loaded["llm"]["endpoint"] == "http://localhost:11434"

    def test_load_config_missing_section_created(self, tmp_path):
        config = {"database": {}, "modes": {}, "personality": {}}
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        loaded = load_config(path)
        assert loaded["database"]["sqlite_path"] == "./data/tomodesk.db"
        assert "memory" in loaded
        assert "llm" in loaded

    def test_load_config_bootstraps_from_example(self, tmp_path):
        example = tmp_path / "config.example.yaml"
        example.write_text(
            yaml.safe_dump(
                {
                    "llm": {"model": "qwen"},
                    "memory": {"max_short_term_messages": 20},
                    "personality": {"pack": "tomo"},
                    "modes": {"proactive": True},
                    "database": {"path": "data/tomodesk.db"},
                }
            ),
            encoding="utf-8",
        )
        target = tmp_path / "config.yaml"
        assert not target.exists()
        loaded = load_config(target)
        assert target.exists()
        assert loaded["llm"]["model"] == "qwen"

    def test_load_config_missing_config_and_example_raises(self, tmp_path, monkeypatch):
        target = tmp_path / "config.yaml"
        empty = tmp_path / "no_example_here"
        empty.mkdir()
        monkeypatch.setattr("src.config.config.resource_dir", lambda: empty)
        with pytest.raises(FileNotFoundError):
            load_config(target)

    def test_load_config_bootstraps_bundled_example(self, tmp_path, monkeypatch):
        import src.config.config as config_mod
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "config.example.yaml").write_text(
            yaml.safe_dump(
                {
                    "llm": {"model": "qwen2"},
                    "memory": {"max_short_term_messages": 20},
                    "personality": {"pack": "tomo"},
                    "modes": {"proactive": True},
                    "database": {},
                }
            ),
            encoding="utf-8",
        )
        cfg_dir = tmp_path / "user_config"
        monkeypatch.setattr(config_mod, "resource_dir", lambda: bundle)
        monkeypatch.setattr(config_mod, "default_config_path",
                            lambda: cfg_dir / "config.yaml")
        config_mod._CONFIG_PATH = None
        try:
            loaded = config_mod.load_config()
            assert loaded["llm"]["model"] == "qwen2"
            created = cfg_dir / "config.yaml"
            assert created.exists()
            assert loaded["database"]["sqlite_path"] == "./data/tomodesk.db"
            assert loaded["database"]["sqlite_path"] not in yaml.safe_load(
                created.read_text(encoding="utf-8")
            ).get("database", {})
        finally:
            config_mod._CONFIG_PATH = None
