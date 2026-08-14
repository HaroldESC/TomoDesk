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

    def test_load_config_missing_config_and_example_raises(self, tmp_path):
        target = tmp_path / "config.yaml"
        with pytest.raises(FileNotFoundError):
            load_config(target)
