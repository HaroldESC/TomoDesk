"""Tests for internationalization module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.config.i18n import I18nManager


@pytest.fixture
def locale_dir():
    """Create temporary locale directory with en.json and es.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        locale_path = Path(tmpdir) / "locales"
        locale_path.mkdir()

        en_data = {
            "greeting": "Hello",
            "nested": {"deep": "Deep value"},
            "placeholder": "Hello {name}"
        }
        es_data = {
            "greeting": "Hola",
            "nested": {"deep": "Valor profundo"},
            "placeholder": "Hola {name}"
        }

        (locale_path / "en.json").write_text(json.dumps(en_data), encoding="utf-8")
        (locale_path / "es.json").write_text(json.dumps(es_data), encoding="utf-8")

        yield locale_path


def test_load_translations(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert "en" in i18n.translations
    assert "es" in i18n.translations
    assert i18n.translations["en"]["greeting"] == "Hello"


def test_detect_language_auto(locale_dir, monkeypatch):
    i18n = I18nManager(str(locale_dir))
    monkeypatch.setattr(i18n, "_detect_windows_lang", lambda: None)
    monkeypatch.setattr("locale.getlocale", lambda *_: ("es_ES", "UTF-8"))
    lang = i18n.detect_language("auto")
    assert lang == "es"

    monkeypatch.setattr("locale.getlocale", lambda *_: (None, None))
    lang = i18n.detect_language("auto")
    assert lang == "en"


def test_detect_language_auto_windows_ui(locale_dir, monkeypatch):
    """Simulate Windows returning es-ES via GetUserDefaultLocaleName."""
    import sys
    import types

    i18n = I18nManager(str(locale_dir))

    class FakeBuffer:
        def __init__(self, size):
            self.value = ""

        def __len__(self):
            return 85

    class FakeKernel32:
        @staticmethod
        def GetUserDefaultLocaleName(buf, size):
            buf.value = "es-ES"
            return 6

    class FakeWindll:
        kernel32 = FakeKernel32()

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.windll = FakeWindll()
    fake_ctypes.create_unicode_buffer = FakeBuffer
    fake_ctypes.c_int = int
    fake_ctypes.wintypes = types.SimpleNamespace(LPWSTR=object)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    assert i18n.detect_language("auto") == "es"


def test_normalize_lang_variants(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n._normalize_lang("en_US") == "en"
    assert i18n._normalize_lang("es-ES") == "es"
    assert i18n._normalize_lang("es_ES.UTF-8") == "es"
    assert i18n._normalize_lang("pt-BR") is None
    assert i18n._normalize_lang(None) is None
    assert i18n._normalize_lang("") is None


def test_detect_language_explicit(locale_dir):
    i18n = I18nManager(str(locale_dir))
    lang = i18n.detect_language("es")
    assert lang == "es"
    lang = i18n.detect_language("fr")
    assert lang == "en"


def test_set_language(locale_dir):
    i18n = I18nManager(str(locale_dir))
    i18n.set_language("es")
    assert i18n.get_current_language() == "es"
    i18n.set_language("xx")
    assert i18n.get_current_language() == "es"


def test_translation_simple(locale_dir):
    i18n = I18nManager(str(locale_dir))
    i18n.set_language("en")
    assert i18n.t("greeting") == "Hello"
    i18n.set_language("es")
    assert i18n.t("greeting") == "Hola"


def test_translation_nested(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("nested.deep") == "Deep value"
    i18n.set_language("es")
    assert i18n.t("nested.deep") == "Valor profundo"


def test_translation_placeholder(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("placeholder", name="World") == "Hello World"
    i18n.set_language("es")
    assert i18n.t("placeholder", name="Mundo") == "Hola Mundo"


def test_missing_key_fallback(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("missing.key") == "missing.key"
    assert i18n.t("nonexistent") == "nonexistent"


def test_missing_placeholder(locale_dir, caplog):
    i18n = I18nManager(str(locale_dir))
    result = i18n.t("placeholder")
    assert "Missing placeholder" in caplog.text
    assert result == "Hello {name}"


def test_load_full_locale_files():
    """Test loading the actual project locale files."""
    i18n = I18nManager("data/locales", default_lang="en")
    assert "en" in i18n.translations
    assert "es" in i18n.translations
    assert i18n.t("app.title", name="Tomo") == "TomoDesk - Tomo"
    assert i18n.t("menu.file") == "&File"
    assert i18n.t("chat.send_button") == "Send"
    assert i18n.t("dialogs.notes.title") == "Notes"
    i18n.set_language("es")
    assert i18n.t("menu.file") == "&Archivo"
    assert i18n.t("chat.send_button") == "Enviar"
    assert i18n.t("dialogs.notes.title") == "Notas"
