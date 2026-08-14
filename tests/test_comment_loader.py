import pytest
import yaml

from src.personality.comment_loader import CommentLoader


def test_load_valid_yaml(tmp_path):
    f = tmp_path / "test.yaml"
    data = {
        "greeting": ["Hello {name}!", "Hi there!"],
        "farewell": ["Goodbye {name}!"],
    }
    f.write_text(yaml.dump(data), encoding="utf-8")

    loader = CommentLoader(str(f))
    assert loader.has_category("greeting")
    assert loader.has_category("farewell")
    assert not loader.has_category("nonexistent")

    phrase = loader.get_random("greeting", {"name": "Tomo"})
    assert phrase is not None

    phrase2 = loader.get_random("farewell", {"name": "Tomo"})
    assert phrase2 is not None
    assert "Tomo" in phrase2


def test_load_empty_yaml(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("", encoding="utf-8")

    loader = CommentLoader(str(f))
    assert loader.phrases == {}


def test_load_missing_file():
    loader = CommentLoader("nonexistent_file.yaml")
    assert loader.phrases == {}


def test_get_random_nonexistent_category(tmp_path):
    f = tmp_path / "test.yaml"
    data = {"greeting": ["Hello"]}
    f.write_text(yaml.dump(data), encoding="utf-8")

    loader = CommentLoader(str(f))
    assert loader.get_random("nonexistent") is None


def test_reload(tmp_path):
    f = tmp_path / "test.yaml"
    data = {"greeting": ["Hello"]}
    f.write_text(yaml.dump(data), encoding="utf-8")

    loader = CommentLoader(str(f))
    assert loader.has_category("greeting")

    data2 = {"farewell": ["Bye"]}
    f.write_text(yaml.dump(data2), encoding="utf-8")

    loader.reload()
    assert not loader.has_category("greeting")
    assert loader.has_category("farewell")
