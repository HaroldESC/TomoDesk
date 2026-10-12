"""Tests for the design system (tokens and generated stylesheets).

Pure-string assertions do not need a QApplication; the ones that apply a
stylesheet to a real widget use the ``qapp`` fixture and are skipped on
Linux without a display server.
"""
import ast
import inspect
import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("qapp")

from src.gui.styles import styles as s

# #RGB o #RRGGBB, sin admitir formas más largas (evita falsos positivos con
# identificadores tipo #abc1234).
_HEX_LITERAL = re.compile(r"#[0-9A-Fa-f]{6}(?![0-9A-Fa-f])|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])")


class TestStyleSetContract:
    def test_returns_exactly_three_keys(self):
        for theme in ("light", "dark"):
            style_set = s.get_style_set(theme)
            assert set(style_set) == {"main", "dialog", "overlay_menu"}

    def test_all_values_are_non_empty_strings(self):
        for theme in ("light", "dark"):
            for name, qss in s.get_style_set(theme).items():
                assert isinstance(qss, str), f"{theme}/{name} is not a string"
                assert qss.strip(), f"{theme}/{name} is empty"

    def test_values_are_the_module_constants(self):
        """Callers compare by identity in a few places; keep them shared."""
        assert s.get_style_set("dark")["main"] is s.MAIN_STYLE_DARK
        assert s.get_style_set("light")["main"] is s.MAIN_STYLE
        assert s.get_style_set("dark")["dialog"] is s.DIALOG_STYLE_DARK
        assert s.get_style_set("light")["overlay_menu"] is s.OVERLAY_MENU_STYLE

    @pytest.mark.parametrize("theme", ["light", "", None, "DARK", "neon", "MiDNiGhT"])
    def test_anything_but_dark_falls_back_to_light(self, theme):
        """Theme matching is exact and case-sensitive: unknown means light."""
        assert s.get_style_set(theme)["main"] is s.MAIN_STYLE

    def test_default_argument_is_light(self):
        assert s.get_style_set()["main"] is s.MAIN_STYLE


class TestTokenParity:
    def test_both_themes_declare_the_same_tokens(self):
        assert set(s._LIGHT_TOKENS) == set(s._DARK_TOKENS)

    @pytest.mark.parametrize("token", sorted(s._LIGHT_TOKENS))
    def test_every_token_is_defined_in_both_themes(self, token):
        assert token in s._LIGHT_TOKENS
        assert token in s._DARK_TOKENS

    def test_tokens_are_non_empty_hex_or_shorthand(self):
        for name, tokens in (("light", s._LIGHT_TOKENS), ("dark", s._DARK_TOKENS)):
            for token, value in tokens.items():
                assert value, f"{name}/{token} is empty"
                assert "#" in value or "none" in value, f"{name}/{token}={value!r}"

    def test_palettes_differ_on_key_tokens(self):
        """No exigimos que TODOS difieran: algunos tokens son compartidos
        a proposito (p. ej. TEXT_ON_ACCENT es blanco en ambos temas)."""
        differing = [
            t for t in s._LIGHT_TOKENS if s._LIGHT_TOKENS[t] != s._DARK_TOKENS[t]
        ]
        assert len(differing) >= 10, f"solo {len(differing)} tokens difieren"
        # Los que definen la identidad de cada tema deben diferir seguro.
        for token in ("bg_window", "bg_surface", "text_primary", "border", "accent"):
            assert s._LIGHT_TOKENS[token] != s._DARK_TOKENS[token], token

    def test_dark_window_background_is_different_from_light(self):
        assert s.BG_WINDOW_DK != s.BG_WINDOW
        assert s.MAIN_STYLE_DARK != s.MAIN_STYLE


class TestGeneratedQss:
    def test_no_leaked_python_subscript(self):
        """_build_main_qss interpolates by subscript; a bug leaks 'c['."""
        for name, qss in (
            ("MAIN_STYLE", s.MAIN_STYLE),
            ("MAIN_STYLE_DARK", s.MAIN_STYLE_DARK),
            ("DIALOG_STYLE", s.DIALOG_STYLE),
            ("DIALOG_STYLE_DARK", s.DIALOG_STYLE_DARK),
            ("OVERLAY_MENU_STYLE", s.OVERLAY_MENU_STYLE),
            ("OVERLAY_MENU_STYLE_DARK", s.OVERLAY_MENU_STYLE_DARK),
        ):
            assert "c[" not in qss, f"{name} leaked a token subscript"
            assert "{c" not in qss, f"{name} leaked an unformatted placeholder"

    def test_dialog_style_includes_the_main_style(self):
        assert s.DIALOG_STYLE.endswith(s.MAIN_STYLE)
        assert s.DIALOG_STYLE_DARK.endswith(s.MAIN_STYLE_DARK)

    def test_dark_sheet_uses_the_dark_window_background(self):
        assert s.BG_WINDOW_DK in s.MAIN_STYLE_DARK
        assert s.BG_WINDOW in s.MAIN_STYLE
        assert s.BG_WINDOW not in s.MAIN_STYLE_DARK, "light bg leaked into dark"
        assert s.BG_WINDOW_DK not in s.MAIN_STYLE, "dark bg leaked into light"

    def test_dark_sheet_uses_the_dark_text_color(self):
        assert s.TEXT_PRIMARY_DK in s.MAIN_STYLE_DARK
        assert s.TEXT_PRIMARY in s.MAIN_STYLE

    def test_scrollbars_are_narrowed_in_both_themes(self):
        for qss in (s.MAIN_STYLE, s.MAIN_STYLE_DARK):
            assert "QScrollBar:vertical" in qss
            assert "0px" in qss

    def test_error_label_style_exists(self):
        for qss in (s.MAIN_STYLE, s.MAIN_STYLE_DARK):
            assert "#error" in qss

    def test_settings_navigation_ids_exist(self):
        """El diálogo de Ajustes depende de estos objectName."""
        for qss in (s.MAIN_STYLE, s.MAIN_STYLE_DARK):
            assert "#settings_nav" in qss
            assert "#settings_sidebar" in qss


class TestStylesAppliedToWidgets:
    """The sheets Qt accepts are the ones the app really uses."""

    @pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server",
    )
    @pytest.mark.parametrize("theme", ["light", "dark"])
    def test_every_sheet_is_accepted_by_qt(self, theme, qtbot, monkeypatch):
        from PySide6.QtWidgets import QWidget

        applied = []
        monkeypatch.setattr(
            "PySide6.QtWidgets.QWidget.setStyleSheet",
            lambda self, sheet: applied.append(sheet),
        )
        widget = QWidget()
        qtbot.addWidget(widget)
        for qss in s.get_style_set(theme).values():
            widget.setStyleSheet(qss)
        assert len(applied) == 3


class TestComponentSheets:
    """Hojas QSS por componente: la GUI no construye QSS a mano (§5.1)."""

    def test_primary_button_style_removed(self):
        """Design.md §2.1: el botón primario NO lleva objectName."""
        assert "#primary" not in s.MAIN_STYLE
        assert "#primary" not in s.MAIN_STYLE_DARK

    def test_base_button_variants_survive(self):
        """Solo se retira #primary; el resto de variantes sigue vivo."""
        for qss in (s.MAIN_STYLE, s.MAIN_STYLE_DARK):
            for selector in ("#secondary", "#flat", "#danger"):
                assert selector in qss, selector
            assert "QPushButton:hover" in qss
            assert "QPushButton:pressed" in qss
            assert "QPushButton:disabled" in qss

    def test_chat_frame_qss_per_theme(self):
        light = s.chat_frame_qss("light")
        dark = s.chat_frame_qss("dark")
        assert s.BG_WINDOW in light
        assert s.BG_WINDOW_DK in dark
        assert s.BG_WINDOW not in dark, "fondo claro filtrado al tema oscuro"
        assert "border: 1.5px solid" in light
        assert "border: 1.5px solid" in dark
        assert "border-radius: 12px" in light
        # El área de desplazamiento no debe dibujar marco propio.
        assert "QScrollArea" in light
        assert "border: none" in light

    def test_chat_bubble_qss_roles(self):
        for theme, surface, border, system_bg, sys_text in (
            ("light", s.BG_SURFACE, s.BORDER, s.BG_SYSTEM_MSG, s.TEXT_SECONDARY),
            ("dark", s.BG_SURFACE_DK, s.BORDER_DK, s.BG_SYSTEM_MSG_DK, s.TEXT_SECONDARY_DK),
        ):
            user = s.chat_bubble_frame_qss("user", theme)
            assistant = s.chat_bubble_frame_qss("assistant", theme)
            system = s.chat_bubble_frame_qss("system", theme)

            # Radios por rol (Design.md §2.3).
            assert "border-radius: 12px 12px 4px 12px" in user
            assert "border-radius: 12px 12px 12px 4px" in assistant
            assert "border-radius: 8px" in system

            # Solo el asistente lleva borde.
            assert "border:" not in user
            assert "border:" not in system
            assert f"border: 1px solid {border}" in assistant

            # Fondos por rol.
            assert (s.ACCENT_LIGHT if theme == "light" else s.ACCENT_LIGHT_DK) in user
            assert surface in assistant
            assert system_bg in system

            # Etiquetas: color, tamaño y familia con comillas.
            user_label = s.chat_bubble_label_qss("user", theme)
            system_label = s.chat_bubble_label_qss("system", theme)
            for label in (user_label, s.chat_bubble_label_qss("assistant", theme)):
                assert "font-size: 13px" in label
                assert '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif' in label
                assert "background: transparent" in label
                assert "border: none" in label
            assert (s.TEXT_PRIMARY if theme == "light" else s.TEXT_PRIMARY_DK) in user_label
            assert "font-size: 11px" in system_label
            assert sys_text in system_label

    def test_chat_bubble_unknown_role_falls_back_to_system(self):
        frame = s.chat_bubble_frame_qss("robot", "light")
        label = s.chat_bubble_label_qss("robot", "light")
        assert s.BG_SYSTEM_MSG in frame
        assert "border-radius: 8px" in frame
        assert "font-size: 11px" in label

    @pytest.mark.parametrize("style", ["dark", "comic", "flat", "round"])
    def test_every_bubble_style_has_a_recipe(self, style):
        recipe = s.bubble_style_recipe(style)
        assert len(recipe) == 6
        bg, border, width, text, weight, radius = recipe
        assert len(bg) == 3 and all(0 <= c <= 255 for c in bg)
        assert len(border) == 3 and all(0 <= c <= 255 for c in border)
        assert width > 0 and radius > 0
        assert text.startswith("#")
        assert weight in ("400", "600")

    def test_bubble_style_recipe_unknown_falls_back(self):
        assert s.bubble_style_recipe("does_not_exist") == s.bubble_style_recipe("dark")
        assert s.bubble_style_recipe("dark")[0] == (30, 30, 46)
        # Los cuatro estilos son visualmente distintos entre sí.
        recipes = [s.bubble_style_recipe(st) for st in ("dark", "comic", "flat", "round")]
        assert len({r[0] for r in recipes}) == 4
        assert len({r[1] for r in recipes}) == 4

    @pytest.mark.parametrize("style", ["dark", "comic", "flat", "round"])
    def test_bubble_input_palette_returns_three_hex(self, style):
        palette = s.bubble_input_palette(style)
        assert len(palette) == 3
        assert all(value.startswith("#") for value in palette)

    def test_bubble_input_palettes_differ_on_border(self):
        borders = {
            s.bubble_input_palette(style)[2] for style in ("dark", "comic", "flat", "round")
        }
        assert len(borders) == 4

    def test_sprite_preview_qss_visible_in_dark(self):
        """El borde #555 era invisible sobre fondo oscuro: ahora es un token."""
        light = s.sprite_preview_qss("light")
        dark = s.sprite_preview_qss("dark")
        assert s.BORDER in light
        assert s.BORDER_DK in dark
        assert "1.5px" in dark
        assert "border-radius: 8px" in dark
        for qss in (light, dark):
            assert "#555" not in qss
            assert "background: transparent" in qss

    def test_danger_hover_constants(self):
        """Los hovers de peligro viven en constantes, no inline en los tokens."""
        assert s._LIGHT_TOKENS["danger_hover"] == s.DANGER_HOVER
        assert s._DARK_TOKENS["danger_hover"] == s.DANGER_HOVER_DK
        assert s.DANGER_HOVER != s.DANGER_HOVER_DK
        assert s.DANGER_HOVER in s.MAIN_STYLE
        assert s.DANGER_HOVER_DK in s.MAIN_STYLE_DARK

    def test_component_sheet_sources_carry_no_hex_literals(self):
        """Las hojas nuevas interpolar tokens: ni un hex en su código fuente."""
        for builder in (
            s.chat_frame_qss,
            s.chat_bubble_frame_qss,
            s.chat_bubble_label_qss,
            s.bubble_style_recipe,
            s.bubble_input_palette,
            s.sprite_preview_qss,
        ):
            source = inspect.getsource(builder)
            assert _HEX_LITERAL.search(source) is None, builder.__name__


class TestNoHexOutsideStyles:
    """Design.md §5.1: los hex solo viven en ``styles.py``."""

    def test_no_hex_literals_outside_styles(self):
        gui_root = Path(s.__file__).resolve().parents[1]  # src/gui
        offenders: dict[str, list[str]] = {}
        for path in sorted(gui_root.rglob("*.py")):
            if path.name == "styles.py" or "data" in path.parts:
                continue
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.strip()
                if code.startswith("#"):
                    continue  # comentario de línea
                match = _HEX_LITERAL.search(code)
                if match:
                    offenders.setdefault(str(path.relative_to(gui_root.parent)), []).append(
                        f"line {lineno}: {match.group(0)}"
                    )
        assert not offenders, "hex literales fuera de styles.py: " + repr(offenders)


class TestStartupTheme:
    """El arranque debe respetar el tema de config.

    Regresion: main.py aplicaba siempre MAIN_STYLE (claro), asi que un
    usuario con theme: dark veia la ventana principal en claro hasta que
    Settings re-aplicaba el tema.
    """

    def _run_gui_setstylesheet_calls(self):
        import main

        source = Path(inspect.getsourcefile(main)).read_text(encoding="utf-8")
        run_gui = next(
            n for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.FunctionDef) and n.name == "run_gui"
        )
        return [
            n for n in ast.walk(run_gui)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "setStyleSheet"
        ], run_gui

    def test_run_gui_applies_a_theme_dependent_sheet(self):
        calls, _run_gui = self._run_gui_setstylesheet_calls()
        assert calls, "run_gui no aplica ninguna hoja de estilo"
        # El argumento debe derivarse del tema, no de una constante fija.
        assert "theme" in ast.unparse(calls[0].args[0])

    def test_run_gui_reads_the_configured_theme(self):
        _calls, run_gui = self._run_gui_setstylesheet_calls()
        body = ast.unparse(run_gui)
        assert 'get(\'ui\', {}).get(\'theme\'' in body or 'get("ui", {}).get("theme"' in body
