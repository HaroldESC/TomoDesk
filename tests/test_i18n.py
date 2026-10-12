"""Tests for internationalization module."""

import json
import re
import tempfile
from pathlib import Path

import pytest

from src.config.i18n import I18nManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = PROJECT_ROOT / "data" / "locales"


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


def test_default_used_when_key_missing(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("does.not.exist", default="Fallback text") == "Fallback text"


def test_default_is_formatted_with_kwargs(locale_dir):
    i18n = I18nManager(str(locale_dir))
    result = i18n.t("nope", default="Hello {name}", name="Ana")
    assert result == "Hello Ana"


def test_default_ignored_when_key_exists(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("greeting", default="unused") == "Hello"


def test_missing_key_without_default_returns_key(locale_dir):
    i18n = I18nManager(str(locale_dir))
    assert i18n.t("totally.unknown") == "totally.unknown"


class TestMoodLabels:
    """Los nombres de mood salen de los locales, no de literales en inglés."""

    @pytest.mark.parametrize("lang", ["en", "es"])
    def test_mood_names_are_translated(self, lang):
        from src.config.i18n import I18nManager as M

        i18n = M(str(LOCALES_DIR), default_lang=lang)
        i18n.set_language(lang)
        for key in ("happiness", "energy", "curiosity", "closeness", "connection"):
            label = i18n.t(f"status.mood_name_{key}")
            # Nunca debe devolver la claveave cruda.
            assert label != f"status.mood_name_{key.replace('_name','')}"
            assert label.strip() != ""

    def test_mood_value_lines_render_value(self):
        i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
        i18n.set_language("en")
        line = i18n.t("status.mood_happiness", value=0.75)
        assert "0.75" in line


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
    """Test loading the actual project locale files.

    Usa una ruta absoluta para no depender del directorio de trabajo y la
    version real del paquete, que antes estaba fija en 1.2.0.
    """
    from src import __version__

    i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
    assert "en" in i18n.translations
    assert "es" in i18n.translations

    assert i18n.t("app.title", name="Tomo") == "TomoDesk - Tomo"
    assert i18n.t("chat.send_button") == "Send"
    assert i18n.t("dialogs.notes.title") == "Notes"

    body = i18n.t("app.about_text", name="Tomo", model="llama", version=__version__)
    assert f"TomoDesk v{__version__}" in body
    assert "Character: Tomo" in body and "Model: llama" in body

    assert i18n.t("status.listening", name="Tomo") == "Tomo is listening."
    assert i18n.t("commands.clear_success", name="Tomo") == (
        "Short-term memory cleared. Tomo will not remember this conversation."
    )

    i18n.set_language("es")
    assert i18n.t("chat.send_button") == "Enviar"
    assert i18n.t("dialogs.notes.title") == "Notas"
    assert i18n.t("status.curious", name="Tomo") == (
        "Tomo tiene curiosidad por lo que haces..."
    )
    assert i18n.t("commands.clear_success", name="Tomo") != ""


def test_locale_files_declare_the_same_keys():
    """EN y ES deben evolucionar a la par: sin claves huérfanas."""
    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    es = json.loads((LOCALES_DIR / "es.json").read_text(encoding="utf-8"))

    def flatten(data, prefix=""):
        out = set()
        for key, value in data.items():
            dotted = f"{prefix}{key}"
            if isinstance(value, dict):
                out |= flatten(value, dotted + ".")
            else:
                out.add(dotted)
        return out

    only_en = flatten(en) - flatten(es)
    only_es = flatten(es) - flatten(en)
    assert not only_en, f"claves solo en EN: {sorted(only_en)}"
    assert not only_es, f"claves solo en ES: {sorted(only_es)}"


def test_placeholders_match_between_languages():
    """Las plantillas {x} deben coincidir para no romper el formateo."""
    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    es = json.loads((LOCALES_DIR / "es.json").read_text(encoding="utf-8"))

    def flatten(data, prefix=""):
        out = {}
        for key, value in data.items():
            dotted = f"{prefix}{key}"
            if isinstance(value, dict):
                out.update(flatten(value, dotted + "."))
            else:
                out[dotted] = value
        return out

    fe, fs = flatten(en), flatten(es)
    for key, text in fe.items():
        assert set(re.findall(r"\{(\w+)", text)) == set(
            re.findall(r"\{(\w+)", fs[key])
        ), f"placeholders distintos en {key}"


def test_keys_used_by_the_ui_exist():
    """Evita que la UI muestre el nombre de la clave en claro.

    Recoge las claves literales de .t() mas las que se construyen por
    variable (moods y modos de window-sitting).
    """
    from src.config.i18n import I18nManager as M

    en = json.loads((LOCALES_DIR / "en.json").read_text(encoding="utf-8"))
    es = json.loads((LOCALES_DIR / "es.json").read_text(encoding="utf-8"))

    def flatten(data, prefix=""):
        out = set()
        for key, value in data.items():
            dotted = f"{prefix}{key}"
            if isinstance(value, dict):
                out |= flatten(value, dotted + ".")
            else:
                out.add(dotted)
        return out

    defined = flatten(en) & flatten(es)

    used = set()
    for path in list(PROJECT_ROOT.glob("src/**/*.py")) + [PROJECT_ROOT / "main.py"]:
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r"""\.t\(\s*[fr]?["']([a-zA-Z0-9_.]+)["']""", text))

    # Claves construidas dinamicamente.
    for mood in ("happiness", "energy", "curiosity", "closeness", "connection"):
        used.add(f"status.mood_{mood}")
        used.add(f"status.mood_name_{mood}")
    for mode in ("active", "mouse", "closest", "fixed"):
        used.add(f"dialogs.settings.ws_target_{mode}")
    for pos in ("top_left", "top_right", "bottom_left", "bottom_right"):
        used.add(f"dialogs.settings.ws_fallback_{pos}")
    # El combo de estilo de burbuja itera el enum: las etiquetas se montan
    # por variable, igual que los modos de window-sitting.
    for style in ("dark", "comic", "flat", "round"):
        used.add(f"dialogs.settings.bubble_style_{style}")

    missing = sorted(key for key in used if key not in defined)
    assert not missing, f"claves usadas y no definidas: {missing}"


# Claves anadidas al corregir textos hardcodeados y estados del asistente.
NEW_UI_KEYS = [
    "app.about_powered_by",
    "chat.input_placeholder",
    "chat.commands_tooltip",
    "setup.cancelling",
    # Combos con texto traducido (Fase 2).
    "dialogs.settings.language_auto",
    "dialogs.settings.language_en",
    "dialogs.settings.language_es",
    "dialogs.settings.theme_light",
    "dialogs.settings.theme_dark",
    "dialogs.settings.position_bottom_right",
    "dialogs.settings.position_bottom_left",
    "dialogs.settings.position_top_right",
    "dialogs.settings.position_top_left",
    "dialogs.settings.position_center",
    "dialogs.settings.bubble_style_dark",
    "dialogs.settings.bubble_style_comic",
    "dialogs.settings.bubble_style_flat",
    "dialogs.settings.bubble_style_round",
    # Iconos de la barra de estado y progreso de descarga.
    "dialogs.settings.status_icons",
    "dialogs.settings.status_icons_tip",
    "dialogs.settings.download_bytes",
]


def _lookup(data, key):
    current = data
    for part in key.split("."):
        assert isinstance(current, dict), f"{key} no es una hoja"
        assert part in current, f"falta la clave {key}"
        current = current[part]
    return current


@pytest.mark.parametrize("key", NEW_UI_KEYS)
@pytest.mark.parametrize("lang", ["en", "es"])
def test_new_keys_exist_and_are_translated(key, lang):
    """Las claves nuevas existen en ambos locales y no son la clave cruda."""
    data = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    text = _lookup(data, key)
    assert isinstance(text, str)
    assert text.strip() != ""
    assert text != key


@pytest.mark.parametrize("lang", ["en", "es"])
def test_input_placeholder_does_not_promise_ctrl_enter(lang):
    """El input es de una sola linea: Enter ya envia, no existe Ctrl+Enter."""
    i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
    i18n.set_language(lang)
    placeholder = i18n.t("chat.input_placeholder")
    assert "Ctrl+Enter" not in placeholder
    assert placeholder != "chat.input_placeholder"
    i18n.set_language("en" if lang == "es" else "es")
    assert i18n.t("chat.input_placeholder") != placeholder


@pytest.mark.parametrize("lang", ["en", "es"])
def test_commands_tooltip_lists_the_real_commands(lang):
    """El tooltip del input debe listar comandos que existen de verdad."""
    i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
    i18n.set_language(lang)
    tooltip = i18n.t("chat.commands_tooltip")
    assert tooltip != "chat.commands_tooltip"
    for command in ("/help", "/note", "/remind", "/remember", "/memories",
                    "/mood", "/context", "/proactive", "/model", "/debug",
                    "/exit"):
        assert command in tooltip, f"{command} no aparece en el tooltip"


@pytest.mark.parametrize("lang", ["en", "es"])
def test_commands_tooltip_only_lists_known_commands(lang):
    """Cada comando del tooltip existe en el despachador de ``commands``."""
    source = (
        PROJECT_ROOT / "src" / "system" / "commands.py"
    ).read_text(encoding="utf-8")
    known = set(re.findall(r'"/([a-z_]+)":\s*cmd_', source))

    i18n = I18nManager(str(LOCALES_DIR), default_lang="en")
    i18n.set_language(lang)
    listed = set(re.findall(r"/([a-z_]+)", i18n.t("chat.commands_tooltip")))

    assert listed, "el tooltip deberia listar comandos"
    assert listed <= known, f"comandos inexistentes en el tooltip: {listed - known}"
