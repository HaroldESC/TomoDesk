# TomoDesk — UI Redesign Specification

---

## 1. Sistema de Diseño

### 1.1 Tokens de Color

Definir como constantes Python al inicio de `src/gui/styles.py`. Todo QSS usa estas constantes — ningún código hex en otros archivos.

```python
# Fondos
BG_WINDOW      = "#F5F5FA"   # Ventana principal, paneles
BG_SURFACE     = "#FFFFFF"   # Chat area, tarjetas, diálogos
BG_INPUT       = "#ECECF3"   # Inputs en reposo
BG_HOVER       = "#E4E4EF"   # Hover en botones e items
BG_SYSTEM_MSG  = "#EEEEF6"   # Mensajes de sistema en chat

# Acento — indigo suave (anime/visual novel)
ACCENT         = "#7B85D6"
ACCENT_HOVER   = "#636FC4"
ACCENT_PRESSED = "#4E59B2"
ACCENT_LIGHT   = "#DDE1F7"   # Burbuja usuario, highlights

# Texto
TEXT_PRIMARY   = "#1E1E30"   # Cuerpo principal
TEXT_SECONDARY = "#5C5C7A"   # Etiquetas, subtítulos
TEXT_MUTED     = "#9898B5"   # Placeholders, deshabilitado
TEXT_ON_ACCENT = "#FFFFFF"   # Texto sobre acento

# Bordes
BORDER         = "#D4D4EC"
BORDER_FOCUS   = "#7B85D6"

# Estados
SUCCESS        = "#6DAB8A"
WARNING        = "#E0A060"
DANGER         = "#D97070"
```

### 1.2 Tipografía

- Familia: `"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif`
- Tamaño base: `13px`
- Tamaño pequeño (labels, status): `11px`
- Tamaño grande (títulos de diálogo): `15px`
- Peso normal: `400` | Semi-bold: `600` | Bold: `700`
- **No Comic Sans en ningún componente.**

### 1.3 Geometría

- Radio pequeño: `6px` (checkboxes, separadores)
- Radio medio: `8px` (inputs, botones, items de lista)
- Radio grande: `12px` (burbujas chat, diálogos, panels)
- Padding input: `7px 12px`
- Padding botón: `7px 18px`

---

## 2. Cambios por Archivo

### 2.1 `src/gui/styles.py` — Reemplazar completamente

**Producir exactamente este contenido:**

```python
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

# ── Estilo principal (aplicado a MainWindow) ─────────────────────────────────
MAIN_STYLE = f"""

/* ── Global ──────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {BG_WINDOW};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

/* ── Barra de menú ───────────────────────────────────────────────── */
QMenuBar {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
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
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── Menús desplegables ──────────────────────────────────────────── */
QMenu {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
    font-size: 13px;
}}
QMenu::item:selected {{
    background-color: {ACCENT_LIGHT};
    color: {TEXT_PRIMARY};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 10px;
}}

/* ── Barra de estado ──────────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER};
    font-size: 11px;
    padding: 2px 10px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Botones ─────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {ACCENT};
    color: {TEXT_ON_ACCENT};
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 70px;
}}
QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton:pressed {{
    background-color: {ACCENT_PRESSED};
}}
QPushButton:disabled {{
    background-color: {BG_INPUT};
    color: {TEXT_MUTED};
}}

QPushButton#secondary {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    font-weight: 400;
}}
QPushButton#secondary:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_FOCUS};
}}
QPushButton#secondary:pressed {{
    background-color: {BG_HOVER};
}}

QPushButton#flat {{
    background: transparent;
    color: {TEXT_SECONDARY};
    border: none;
    padding: 4px 8px;
    min-width: 0;
    font-weight: 400;
}}
QPushButton#flat:hover {{
    color: {ACCENT};
    background-color: {ACCENT_LIGHT};
    border-radius: 6px;
}}
QPushButton#danger {{
    background-color: {DANGER};
    color: {TEXT_ON_ACCENT};
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
}}
QPushButton#danger:hover {{
    background-color: #C85A5A;
}}

/* ── Inputs de texto ──────────────────────────────────────────────── */
QLineEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}
QLineEdit:focus {{
    border-color: {BORDER_FOCUS};
    background-color: {BG_SURFACE};
}}
QLineEdit:disabled {{
    background-color: {BG_WINDOW};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 8px;
    font-size: 13px;
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {BORDER_FOCUS};
}}

/* ── Scroll bars (minimalista) ────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
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
    background: {BORDER};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
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
    color: {TEXT_PRIMARY};
    background: transparent;
}}
QLabel#secondary {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}
QLabel#heading {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

/* ── List widgets ─────────────────────────────────────────────────── */
QListWidget {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
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
    background-color: {ACCENT_LIGHT};
    color: {TEXT_PRIMARY};
}}
QListWidget::item:hover:!selected {{
    background-color: {BG_HOVER};
}}

/* ── Combo box ───────────────────────────────────────────────────── */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 90px;
}}
QComboBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
    padding-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {ACCENT_LIGHT};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}

/* ── Checkbox / Radio ────────────────────────────────────────────── */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {BORDER};
    border-radius: 4px;
    background: {BG_SURFACE};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    font-size: 13px;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    background: {BG_SURFACE};
}}
QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Spin boxes ──────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 13px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {BORDER_FOCUS};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    border: none;
    background: transparent;
    width: 18px;
}}

/* ── Group box ───────────────────────────────────────────────────── */
QGroupBox {{
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
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
    background: {BG_WINDOW};
    color: {TEXT_SECONDARY};
}}

/* ── Tab widget ──────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 0 10px 10px 10px;
    background: {BG_SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: {BG_WINDOW};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 7px 18px;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background: {BG_SURFACE};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

/* ── Message box ─────────────────────────────────────────────────── */
QMessageBox {{
    background-color: {BG_SURFACE};
}}
QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
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
    background: {BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: none;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_HOVER};
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── Tooltip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {TEXT_PRIMARY};
    color: {BG_SURFACE};
    border: none;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}}
"""

# ── Estilo diálogos (MAIN_STYLE + regla QDialog base) ────────────────────────
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

# ── Estilo menú contextual del overlay ───────────────────────────────────────
# Borde oscuro para coherencia con la manga bubble
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
```

---

### 2.2 `src/gui/speech_bubble.py` — Actualizar estilo COMIC a manga real

**Objetivo:** La burbuja estilo `"comic"` pasa a ser una manga bubble auténtica: fondo blanco, borde negro grueso, fuente sans-serif bold. Eliminar Comic Sans. La arquitectura existente (QPainter, cola triangular) se mantiene.

**Cambio 1 — `_apply_style`, rama `else` (estilo COMIC):**

Reemplazar el bloque `else:` completo con:

```python
else:
    # MANGA / COMIC style — manga speech bubble
    bg_color = QColor(255, 255, 255)
    border_color = QColor(30, 30, 48)   # ~TEXT_PRIMARY
    self.setStyleSheet("""
        QTextEdit {
            color: #1E1E30;
            font-size: 13px;
            font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
            font-weight: 600;
            line-height: 1.4;
        }
    """)
    self._bg_color = bg_color
    self._border_color = border_color
    self._border_width = 2.5
```

En la rama `if self.style == BubbleStyle.DARK:` añadir al final:
```python
self._border_width = 1.5
```

**Cambio 2 — `paintEvent`, reemplazar la línea `pen = QPen(...)` y `painter.drawPath(...)` con:**

```python
pen = QPen(self._border_color, self._border_width)
pen.setJoinStyle(Qt.MiterJoin)   # esquinas afiladas en la cola, estilo manga
pen.setCapStyle(Qt.RoundCap)
painter.setPen(pen)

# Primero relleno, luego borde (orden importa para que el borde quede encima)
painter.fillPath(path, QBrush(self._bg_color))
painter.drawPath(path)
```

**Cambio 3 — aumentar el tamaño de la cola** para que sea más visible:

Cambiar `tail_width = 16` → `tail_width = 20`
Cambiar `tail_height = 10` → `tail_height = 13`

**Cambio 4 — añadir import `Qt` si no está:**
```python
from PySide6.QtCore import Qt, QTimer
```

**Sin cambios en la interfaz pública.** `show_text()`, `show_thinking()`, `hide_bubble()` y `set_style()` no cambian. El YAML sigue usando `ui.bubble_style: "comic"`.

---

### 2.3 `src/gui/tray_icon.py` — i18n + icono mejorado

**Objetivo:** Usar i18n en todas las cadenas del menú (actualmente están hardcodeadas en inglés). Mejorar el icono programático.

**Cambio 1 — Firma de `__init__`:**

```python
def __init__(self, main_window, config, overlay=None, i18n=None, parent=None):
    super().__init__(parent)
    self.main_window = main_window
    self.config = config
    self.overlay = overlay
    self.i18n = i18n
    self._setup_icon()
    self._setup_menu()
    self._connect_signals()
    self.show()
    logger.info("Tray icon created")
```

**Cambio 2 — Reemplazar `_setup_icon` completo:**

```python
def _setup_icon(self):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    # Fondo redondeado en color acento
    painter.setBrush(QColor("#7B85D6"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    # Letra T centrada
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Segoe UI", 26, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "T")
    painter.end()
    self.setIcon(QIcon(pixmap))
    name = self.config.get("personality", {}).get("name", "Tomo")
    self.setToolTip(f"TomoDesk — {name}")
```

**Cambio 3 — Reemplazar `_setup_menu` completo:**

```python
def _setup_menu(self):
    t = self.i18n.t if self.i18n else (lambda key, **kw: key)
    menu = QMenu()

    show_action = QAction(t("menu.show_chat"), self)
    show_action.triggered.connect(self._show_main_window)
    menu.addAction(show_action)

    menu.addSeparator()

    notes_action = QAction(t("menu.notes"), self)
    notes_action.triggered.connect(self.main_window._open_notes)
    menu.addAction(notes_action)

    reminders_action = QAction(t("menu.reminders"), self)
    reminders_action.triggered.connect(self.main_window._open_reminders)
    menu.addAction(reminders_action)

    menu.addSeparator()

    self.focus_action = QAction(t("menu.focus_mode"), self)
    self.focus_action.setCheckable(True)
    self.focus_action.triggered.connect(self._toggle_focus)
    menu.addAction(self.focus_action)

    menu.addSeparator()

    exit_action = QAction(t("menu.exit"), self)
    exit_action.triggered.connect(self._exit_app)
    menu.addAction(exit_action)

    self.setContextMenu(menu)
```

**Cambio 4 — Actualizar el llamador en `main.py`:**

Buscar donde se instancia `TrayIcon` y añadir `i18n=i18n`:
```python
tray = TrayIcon(main_window, config, overlay=overlay, i18n=i18n)
```

---

### 2.4 `src/gui/overlay_window.py` — Inline input + menú contextual

**Objetivo:** Estilizar el `inline_input` para que sea coherente con la manga bubble. Aplicar `OVERLAY_MENU_STYLE` al menú contextual.

**Cambio 1 — Import:**
```python
from src.gui.styles import OVERLAY_MENU_STYLE
```

**Cambio 2 — En `_show_inline_input`, añadir `setStyleSheet` al input:**

Dentro del bloque `if self.inline_input is None:`, después de crear el widget y antes de `self.inline_input.installEventFilter(self)`:

```python
self.inline_input.setStyleSheet("""
    QLineEdit {
        background-color: #FFFFFF;
        color: #1E1E30;
        border: 2.5px solid #1E1E30;
        border-radius: 8px;
        padding: 5px 10px;
        font-family: "Segoe UI", "Inter", Arial, sans-serif;
        font-size: 12px;
        font-weight: 600;
    }
    QLineEdit:focus {
        border-color: #7B85D6;
    }
""")
```

**Cambio 3 — En `contextMenuEvent`, añadir `setStyleSheet` al menú:**

En la primera línea tras `menu = QMenu(self)`:
```python
menu.setStyleSheet(OVERLAY_MENU_STYLE)
```

---

### 2.5 `src/gui/chat_widget.py` — Burbujas de chat

**IMPORTANTE:** El agente debe leer `chat_widget.py` completo antes de implementar esta sección. Las instrucciones se adaptan según la implementación actual.

#### Si el widget usa `QTextBrowser` con HTML (`.append()` o `.setHtml()`):

Añadir `html.escape` para sanitizar texto antes de insertar:
```python
import html as html_lib
escaped = html_lib.escape(text)
```

Usar este HTML por rol:

**Usuario:**
```python
html = (
    f'<div style="text-align:right; margin:5px 2px;">'
    f'<span style="display:inline-block; background:#DDE1F7; color:#1E1E30;'
    f'border-radius:12px 12px 4px 12px; padding:8px 14px;'
    f'font-family:Segoe UI,Inter,Arial; font-size:13px; max-width:72%;">'
    f'{escaped}</span></div>'
)
```

**Asistente:**
```python
html = (
    f'<div style="text-align:left; margin:5px 2px;">'
    f'<span style="display:inline-block; background:#FFFFFF; color:#1E1E30;'
    f'border:1px solid #D4D4EC; border-radius:12px 12px 12px 4px;'
    f'padding:8px 14px; font-family:Segoe UI,Inter,Arial; font-size:13px; max-width:72%;">'
    f'{escaped}</span></div>'
)
```

**Sistema:**
```python
html = (
    f'<div style="text-align:center; margin:4px 0;">'
    f'<span style="display:inline-block; background:#EEEEF6; color:#5C5C7A;'
    f'border-radius:8px; padding:4px 14px;'
    f'font-family:Segoe UI,Inter,Arial; font-size:11px;">'
    f'{escaped}</span></div>'
)
```

**Fondo del contenedor** (`QTextBrowser` o su padre):
```python
widget.setStyleSheet("""
    QTextBrowser {
        background-color: #F5F5FA;
        border: 1.5px solid #D4D4EC;
        border-radius: 12px;
        padding: 8px;
    }
""")
```

#### Si el widget usa `QWidget` individuales por mensaje:

Cada widget de mensaje debe tener:
- Usuario: `setStyleSheet("background:#DDE1F7; border-radius:12px 12px 4px 12px; padding:8px 14px;")` + alineación derecha
- Asistente: `setStyleSheet("background:#FFFFFF; border:1px solid #D4D4EC; border-radius:12px 12px 12px 4px; padding:8px 14px;")` + alineación izquierda
- Sistema: `setStyleSheet("background:#EEEEF6; border-radius:8px; padding:4px 14px;")` + centrado

---

### 2.6 Diálogos — Aplicar `DIALOG_STYLE`

**Archivos:** `notes_dialog.py`, `reminders_dialog.py`, `memories_dialog.py`, `settings_dialog.py`

**Cambio en cada `__init__`:**
```python
from src.gui.styles import DIALOG_STYLE

class XxxDialog(QDialog):
    def __init__(self, ...):
        super().__init__(parent)
        self.setStyleSheet(DIALOG_STYLE)
        # resto sin cambios
```

**Tamaño mínimo en todos los diálogos:**
```python
self.setMinimumSize(500, 360)
```

**Centrado en ventana padre** — añadir a cada diálogo si no existe:
```python
def showEvent(self, event):
    super().showEvent(event)
    if self.parent():
        p = self.parent().geometry()
        self.move(
            p.x() + (p.width() - self.width()) // 2,
            p.y() + (p.height() - self.height()) // 2,
        )
```

**Botones en diálogos:**
- El botón de acción primaria (Guardar, Añadir, Aceptar) → sin objectName → estilo acento por defecto.
- El botón de cancelar/cerrar → `btn.setObjectName("secondary")`.
- El botón de eliminar → `btn.setObjectName("danger")`.

---

### 2.7 `src/gui/main_window.py` — Status bar compacta

**Objetivo:** El status bar muestra demasiado texto. Hacerlo compacto y legible.

**Reemplazar `_update_status` completo:**

```python
def _update_status(self):
    parts = []
    if self.state_manager:
        s = self.state_manager.get_state()
        parts.append(f"❤ {s['happiness']:.2f}")
        parts.append(f"⚡ {s['energy']:.2f}")
        parts.append(f"✦ {s['curiosity']:.2f}")
        parts.append(f"☁ {s['closeness']:.2f}")
    if self.proactive_engine:
        try:
            enabled = self.proactive_engine.policy.is_enabled()
            parts.append("🔔" if enabled else "🔕")
        except Exception:
            pass
    self.status.showMessage("   ".join(parts))
```

---

## 3. Claves i18n a Verificar/Añadir

Revisar `data/locales/en.json` y `es.json`. Añadir si no existen:

| Clave | Inglés | Español |
|---|---|---|
| `menu.show_chat` | `"Show Chat"` | `"Mostrar Chat"` |
| `menu.focus_mode` | `"Focus Mode"` | `"Modo Foco"` |
| `menu.configuration` | `"Settings"` | `"Configuración"` |

Si `menu.chat` ya existe y se usa para "Show Chat", reutilizar esa clave en vez de crear una nueva.

---

## 4. Orden de Implementación

Seguir este orden para evitar errores de importación:

1. `src/gui/styles.py` — crear/reemplazar primero (todo lo demás lo importa)
2. `src/gui/speech_bubble.py` — cambios de estilo independientes
3. `src/gui/tray_icon.py` — requiere i18n
4. `src/gui/overlay_window.py` — importa `OVERLAY_MENU_STYLE`
5. `src/gui/chat_widget.py` — leer antes de modificar
6. Diálogos — los cuatro, en cualquier orden
7. `src/gui/main_window.py` — último, depende de que todo lo anterior compile
8. `data/locales/en.json` y `es.json` — verificar claves faltantes

---

## 5. Verificación

Tras implementar todos los cambios:

1. `python main.py --gui` — ventana principal renderiza sin errores
2. Enviar un mensaje de chat — burbuja muestra estilo manga (fondo blanco, borde oscuro, cola)
3. Abrir todos los diálogos desde el menú — verificar que DIALOG_STYLE aplica
4. Click derecho en el overlay — menú contextual con borde oscuro redondeado
5. Click en burbuja del overlay — inline_input con borde oscuro aparece
6. `pytest` — los 206 tests deben pasar sin modificación (los cambios son puramente de presentación)

---

## 6. Fuera de Alcance (próxima sesión)

- Exponer opciones de `config.yaml` como controles UI en `SettingsDialog`
- Selector de pack de personalidad en Settings
- Modo oscuro / toggle de tema
- Ajustes de tamaño de fuente




Puedes hacer clic en las cuatro pestañas para ver cada sección. Los sliders son funcionales y los checkboxes desactivan sus opciones dependientes cuando los apagas.

Algunas decisiones que tomé:

**Organización en 4 pestañas** — Personalidad, Interfaz, Comportamiento, Audio — siguiendo la lógica del `config.yaml`. Todo lo que el usuario toca frecuentemente está en las primeras dos; lo técnico al final.

**Dependencias visuales** — cuando deshabilitas "Comentarios proactivos", el slider de cooldown se atenúa y se deshabilita. Igual con "Sentarse en ventanas" y sus opciones, y con el audio. En Qt esto se implementa con `setEnabled(False)` en los widgets dependientes dentro del `stateChanged` del checkbox.

**Pack de personalidad como lista** en vez de dropdown — tienes pocos packs y vale la pena verlos todos de un vistazo con su descripción.

**Nota de privacidad del audio** — el proyecto ya tiene ese aviso en código, tiene sentido que también aparezca en Settings como referencia permanente.

¿Quieres que añada esto al spec como sección 2.8 con instrucciones concretas para DeepSeek?