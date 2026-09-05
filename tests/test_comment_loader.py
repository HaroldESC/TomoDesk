from pathlib import Path

import pytest
import yaml

from src.personality.comment_loader import CommentLoader


class _FakeI18n:
    def __init__(self, lang):
        self.lang = lang

    def get_current_language(self):
        return self.lang


@pytest.fixture
def lang_dir(tmp_path):
    en_data = {"greeting": ["Hello {name}!"], "farewell": ["Bye!"]}
    es_data = {"greeting": ["¡Hola {name}!"], "farewell": ["¡Adiós!"]}
    (tmp_path / "comments_en.yaml").write_text(
        yaml.dump(en_data), encoding="utf-8")
    (tmp_path / "comments_es.yaml").write_text(
        yaml.dump(es_data), encoding="utf-8")
    return tmp_path


class TestCommentLoaderLang:
    def test_loads_language_file(self, lang_dir):
        loader = CommentLoader(str(lang_dir / "comments_en.yaml"), i18n=_FakeI18n("es"))
        assert loader.get_random("greeting", {"name": "Tomo"}) == "¡Hola Tomo!"

    def test_english_base_file(self, lang_dir):
        loader = CommentLoader(str(lang_dir / "comments_en.yaml"), i18n=_FakeI18n("en"))
        assert loader.get_random("greeting", {"name": "Tomo"}) == "Hello Tomo!"

    def test_falls_back_to_base_path_when_lang_missing(self, lang_dir):
        loader = CommentLoader(str(lang_dir / "comments_en.yaml"), i18n=_FakeI18n("fr"))
        phrase = loader.get_random("greeting", {"name": "Tomo"})
        assert phrase == "Hello Tomo!"

    def test_no_i18n_uses_base_file_directly(self, lang_dir):
        loader = CommentLoader(str(lang_dir / "comments_en.yaml"))
        assert loader.get_random("farewell") == "Bye!"

    def test_real_default_files_load(self):
        base = Path("data/comments_en.yaml")
        if not base.exists():
            pytest.skip("data/comments_en.yaml not shipped in this checkout")
        loader = CommentLoader(str(base), i18n=_FakeI18n("es"))
        for category in ("session_start", "random", "app_opened"):
            phrase = loader.get_random(category, {"window": "Chrome"})
            assert phrase