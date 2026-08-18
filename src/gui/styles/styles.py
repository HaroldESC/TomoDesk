"""
TomoDesk UI Design System
Fuente única de verdad para todo el QSS.
"""

# ── Tokens de color ──────────────────────────────────────────────────────────
BG_WINDOW      = "#F5F5FA"
BG_SURFACE     = "#FFFFFF"
BG_INPUT       = "#ECECF3"
BG_HOVER       = "#E4E4EF"
BG_SYSTEM_MSG  = "#EEEEF6"

ACCENT         = "#7B85D6"
ACCENT_HOVER   = "#636FC4"
ACCENT_PRESSED = "#4E59B2"
ACCENT_LIGHT   = "#DDE1F7"

TEXT_PRIMARY   = "#1E1E30"
TEXT_SECONDARY = "#5C5C7A"
TEXT_MUTED     = "#9898B5"
TEXT_ON_ACCENT = "#FFFFFF"

BORDER         = "#D4D4EC"
BORDER_FOCUS   = "#7B85D6"

SUCCESS        = "#6DAB8A"
WARNING        = "#E0A060"
DANGER         = "#D97070"

# ── Tokens modo oscuro ────────────────────────────────────────────────────────
BG_WINDOW_DK      = "#0F0F1A"
BG_SURFACE_DK     = "#1A1A28"
BG_INPUT_DK       = "#23233A"
BG_HOVER_DK       = "#2A2A44"
BG_SYSTEM_MSG_DK  = "#1E1E30"

ACCENT_DK         = "#9198E0"
ACCENT_HOVER_DK   = "#A5ACEC"
ACCENT_PRESSED_DK = "#7B85D6"
ACCENT_LIGHT_DK   = "#252842"

TEXT_PRIMARY_DK   = "#E6E6F5"
TEXT_SECONDARY_DK = "#8E8EAF"
TEXT_MUTED_DK     = "#4E4E72"
TEXT_ON_ACCENT_DK = "#FFFFFF"

BORDER_DK         = "#282848"
BORDER_FOCUS_DK   = "#9198E0"

SUCCESS_DK        = "#7DC49A"
WARNING_DK        = "#E8B870"
DANGER_DK         = "#E07878"

# ── Generador de QSS por tema ──────────────────────────────────────────────────
def _build_main_qss(c: dict) -> str:
    return f"""
/* ── Global ──────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {c["bg_window"]};
    color: {c["text_primary"]};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ── Barra de menú ───────────────────────────────────────────────── */
QMenuBar {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border-bottom: 1px solid {c["border"]};
    padding: 1px 4px;
    spacing: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 6px;
}}
QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background-color: {c["bg_hover"]};
    color: {c["text_primary"]};
}}

/* ── Menús desplegables ──────────────────────────────────────────── */
QMenu {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
    font-size: 13px;
}}
QMenu::item:selected {{
    background-color: {c["accent_light"]};
    color: {c["text_primary"]};
}}
QMenu::separator {{
    height: 1px;
    background: {c["border"]};
    margin: 4px 10px;
}}

/* ── Barra de estado ──────────────────────────────────────────────── */
QStatusBar {{
    background-color: {c["bg_surface"]};
    color: {c["text_secondary"]};
    border-top: 1px solid {c["border"]};
    font-size: 11px;
    padding: 2px 10px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Botones ─────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {c["accent"]};
    color: {c["text_on_accent"]};
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 70px;
}}
QPushButton:hover {{
    background-color: {c["accent_hover"]};
}}
QPushButton:pressed {{
    background-color: {c["accent_pressed"]};
}}

QPushButton#primary {{
    background-color: {c["accent"]};
    color: {c["text_on_accent"]};
    border: 2px solid {c["accent"]};
    border-radius: 8px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 700;
    min-width: 70px;
}}
QPushButton#primary:hover {{
    background-color: {c["accent_hover"]};
    border-color: {c["accent_hover"]};
}}
QPushButton#primary:pressed {{
    background-color: {c["accent_pressed"]};
    border-color: {c["accent_pressed"]};
}}

QPushButton:disabled {{
    background-color: {c["bg_input"]};
    color: {c["text_muted"]};
}}

QPushButton#secondary {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    font-weight: 400;
}}
QPushButton#secondary:hover {{
    background-color: {c["bg_hover"]};
    border-color: {c["border_focus"]};
}}
QPushButton#secondary:pressed {{
    background-color: {c["bg_hover"]};
}}

QPushButton#flat {{
    background: transparent;
    color: {c["text_secondary"]};
    border: none;
    padding: 4px 8px;
    min-width: 0;
    font-weight: 400;
}}
QPushButton#flat:hover {{
    color: {c["accent"]};
    background-color: {c["accent_light"]};
    border-radius: 6px;
}}
QPushButton#danger {{
    background-color: {c["danger"]};
    color: {c["text_on_accent"]};
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
}}
QPushButton#danger:hover {{
    background-color: {c["danger_hover"]};
}}

/* ── Inputs de texto ──────────────────────────────────────────────── */
QLineEdit {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: {c["accent_light"]};
    selection-color: {c["text_primary"]};
}}
QLineEdit:focus {{
    border-color: {c["border_focus"]};
    background-color: {c["bg_surface"]};
}}
QLineEdit:disabled {{
    background-color: {c["bg_window"]};
    color: {c["text_muted"]};
    border-color: {c["border"]};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    padding: 8px;
    font-size: 13px;
    selection-background-color: {c["accent_light"]};
    selection-color: {c["text_primary"]};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c["border_focus"]};
}}

/* ── Scroll bars (minimalista) ────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {c["border"]};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c["text_muted"]};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {c["border"]};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c["text_muted"]};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel {{
    color: {c["text_primary"]};
    background: transparent;
}}
QLabel#secondary {{
    color: {c["text_secondary"]};
    font-size: 11px;
}}
QLabel#heading {{
    font-size: 15px;
    font-weight: 700;
    color: {c["text_primary"]};
}}

/* ── List widgets ─────────────────────────────────────────────────── */
QListWidget {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 6px;
    border: none;
}}
QListWidget::item:selected {{
    background-color: {c["accent_light"]};
    color: {c["text_primary"]};
}}
QListWidget::item:hover:!selected {{
    background-color: {c["bg_hover"]};
}}

/* ── Combo box ───────────────────────────────────────────────────── */
QComboBox {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 90px;
}}
QComboBox:focus {{
    border-color: {c["border_focus"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
    padding-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {c["bg_surface"]};
    color: {c["text_primary"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {c["accent_light"]};
    selection-color: {c["text_primary"]};
    outline: none;
}}

/* ── Checkbox / Radio ────────────────────────────────────────────── */
QCheckBox {{
    color: {c["text_primary"]};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {c["border"]};
    border-radius: 4px;
    background: {c["bg_surface"]};
}}
QCheckBox::indicator:checked {{
    background-color: {c["accent"]};
    border-color: {c["accent"]};
}}
QCheckBox::indicator:hover {{
    border-color: {c["border_focus"]};
}}

QRadioButton {{
    color: {c["text_primary"]};
    spacing: 8px;
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    background: {c["bg_surface"]};
}}
QRadioButton::indicator:checked {{
    background-color: {c["accent"]};
    border-color: {c["accent"]};
}}

/* ── Spin boxes ──────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {c["bg_input"]};
    color: {c["text_primary"]};
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 13px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c["border_focus"]};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none;
    background: transparent;
    width: 18px;
}}

/* ── Group box ───────────────────────────────────────────────────── */
QGroupBox {{
    color: {c["text_secondary"]};
    border: 1px solid {c["border"]};
    border-radius: 10px;
    margin-top: 10px;
    padding: 14px 10px 10px 10px;
    font-size: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    padding: 0 6px;
    background: {c["bg_window"]};
    color: {c["text_secondary"]};
}}

/* ── Tab widget ──────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {c["border"]};
    border-radius: 0 10px 10px 10px;
    background: {c["bg_surface"]};
    top: -1px;
}}
QTabBar::tab {{
    background: {c["bg_window"]};
    color: {c["text_secondary"]};
    border: 1px solid {c["border"]};
    border-bottom: none;
    padding: 7px 18px;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: {c["bg_surface"]};
    color: {c["accent"]};
    border-bottom: 2px solid {c["accent"]};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {c["bg_hover"]};
    color: {c["text_primary"]};
}}

/* ── Message box ─────────────────────────────────────────────────── */
QMessageBox {{
    background-color: {c["bg_surface"]};
}}
QMessageBox QLabel {{
    color: {c["text_primary"]};
    font-size: 13px;
    min-width: 220px;
    background: transparent;
}}
QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ── Slider ──────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 4px;
    background: {c["border"]};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {c["accent"]};
    border: none;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {c["accent_hover"]};
}}
QSlider::sub-page:horizontal {{
    background: {c["accent"]};
    border-radius: 2px;
}}

/* ── Ajustes: navegación y búsqueda ──────────────────────────────── */
QWidget#settings_sidebar {{
    background-color: {c["bg_window"]};
    border-right: 1px solid {c["border"]};
}}

QListWidget#settings_nav {{
    background: transparent;
    border: none;
    outline: none;
    padding: 4px;
}}
QListWidget#settings_nav::item {{
    padding: 9px 12px;
    border-radius: 8px;
    color: {c["text_secondary"]};
    border: none;
}}
QListWidget#settings_nav::item:selected {{
    background-color: {c["accent_light"]};
    color: {c["accent_pressed"]};
    font-weight: 600;
}}
QListWidget#settings_nav::item:hover:!selected {{
    background-color: {c["bg_hover"]};
}}

QLineEdit#search_field {{
    background-color: {c["bg_input"]};
    border: 1.5px solid {c["border"]};
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
}}
QLineEdit#search_field:focus {{
    border-color: {c["border_focus"]};
    background-color: {c["bg_surface"]};
}}

QLabel#page_heading {{
    font-size: 16px;
    font-weight: 700;
    color: {c["text_primary"]};
    padding: 2px 0 10px 0;
}}

QLabel#no_results {{
    color: {c["text_muted"]};
    font-size: 13px;
    padding: 6px 2px;
}}

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {c["tooltip_bg"]};
    color: {c["tooltip_fg"]};
    border: {c["tooltip_border"]};
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}}
"""

_LIGHT_TOKENS = {
    "bg_window":      BG_WINDOW,
    "bg_surface":     BG_SURFACE,
    "bg_input":       BG_INPUT,
    "bg_hover":       BG_HOVER,
    "bg_system_msg":  BG_SYSTEM_MSG,
    "accent":         ACCENT,
    "accent_hover":   ACCENT_HOVER,
    "accent_pressed": ACCENT_PRESSED,
    "accent_light":   ACCENT_LIGHT,
    "text_primary":   TEXT_PRIMARY,
    "text_secondary": TEXT_SECONDARY,
    "text_muted":     TEXT_MUTED,
    "text_on_accent": TEXT_ON_ACCENT,
    "border":         BORDER,
    "border_focus":   BORDER_FOCUS,
    "success":        SUCCESS,
    "warning":        WARNING,
    "danger":         DANGER,
    "danger_hover":   "#C85A5A",
    "tooltip_bg":     TEXT_PRIMARY,
    "tooltip_fg":     BG_SURFACE,
    "tooltip_border": "none",
}

_DARK_TOKENS = {
    "bg_window":      BG_WINDOW_DK,
    "bg_surface":     BG_SURFACE_DK,
    "bg_input":       BG_INPUT_DK,
    "bg_hover":       BG_HOVER_DK,
    "bg_system_msg":  BG_SYSTEM_MSG_DK,
    "accent":         ACCENT_DK,
    "accent_hover":   ACCENT_HOVER_DK,
    "accent_pressed": ACCENT_PRESSED_DK,
    "accent_light":   ACCENT_LIGHT_DK,
    "text_primary":   TEXT_PRIMARY_DK,
    "text_secondary": TEXT_SECONDARY_DK,
    "text_muted":     TEXT_MUTED_DK,
    "text_on_accent": TEXT_ON_ACCENT_DK,
    "border":         BORDER_DK,
    "border_focus":   BORDER_FOCUS_DK,
    "success":        SUCCESS_DK,
    "warning":        WARNING_DK,
    "danger":         DANGER_DK,
    "danger_hover":   "#C86060",
    "tooltip_bg":     BG_HOVER_DK,
    "tooltip_fg":     TEXT_PRIMARY_DK,
    "tooltip_border": "1px solid " + BORDER_DK,
}

MAIN_STYLE       = _build_main_qss(_LIGHT_TOKENS)
MAIN_STYLE_DARK  = _build_main_qss(_DARK_TOKENS)

# ── Estilo diálogos ──────────────────────────────────────────────────────────
DIALOG_STYLE = f"""
QDialog {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QDialog > QWidget {{
    background-color: {BG_SURFACE};
}}
""" + MAIN_STYLE

DIALOG_STYLE_DARK = f"""
QDialog {{
    background-color: {BG_SURFACE_DK};
    color: {TEXT_PRIMARY_DK};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QDialog > QWidget {{
    background-color: {BG_SURFACE_DK};
}}
""" + MAIN_STYLE_DARK

# ── Menú contextual del overlay ──────────────────────────────────────────────
OVERLAY_MENU_STYLE = f"""
QMenu {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 2px solid {TEXT_PRIMARY};
    border-radius: 12px;
    padding: 6px;
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 13px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_LIGHT};
    color: {ACCENT_PRESSED};
    font-weight: 600;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 10px;
}}
"""

OVERLAY_MENU_STYLE_DARK = f"""
QMenu {{
    background-color: {BG_SURFACE_DK};
    color: {TEXT_PRIMARY_DK};
    border: 2px solid {ACCENT_DK};
    border-radius: 12px;
    padding: 6px;
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    font-size: 13px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_LIGHT_DK};
    color: {ACCENT_HOVER_DK};
    font-weight: 600;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_DK};
    margin: 4px 10px;
}}
"""

# ── Selector de tema ──────────────────────────────────────────────────────────

def get_style_set(theme: str = "light") -> dict:
    if theme == "dark":
        return {
            "main": MAIN_STYLE_DARK,
            "dialog": DIALOG_STYLE_DARK,
            "overlay_menu": OVERLAY_MENU_STYLE_DARK,
        }
    return {
        "main": MAIN_STYLE,
        "dialog": DIALOG_STYLE,
        "overlay_menu": OVERLAY_MENU_STYLE,
    }
