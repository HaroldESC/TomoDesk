"""Tests for the design system (tokens and generated stylesheets).

Pure-string assertions do not need a QApplication; the ones that apply a
stylesheet to a real widget use the ``qapp`` fixture and are skipped on
Linux without a display server.
"""
import ast
import inspect
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("qapp")

from src.gui.styles import styles as s


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
