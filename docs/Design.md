# TomoDesk — Design Conventions

> Extracto de las especificaciones de UI Redesign para uso como guía de diseño.

---

## 1. Sistema de Diseño

### 1.1 Tokens de Color

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

- **Familia:** `"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif`
- **Tamaño base:** `13px`
- **Tamaño pequeño** (labels, status): `11px`
- **Tamaño grande** (títulos de diálogo): `15px`
- **Pesos:** `400` (normal) | `600` (semi-bold) | `700` (bold)

### 1.3 Geometría

- **Radio pequeño:** `6px` (checkboxes, separadores)
- **Radio medio:** `8px` (inputs, botones, items de lista)
- **Radio grande:** `12px` (burbujas chat, diálogos, panels)
- **Padding input:** `7px 12px`
- **Padding botón:** `7px 18px`

---

## 2. Patrones de Estilo por Componente

### 2.1 Botones

```css
/* Primario (acento) — Sin objectName */
QPushButton {
    background-color: ACCENT;
    color: TEXT_ON_ACCENT;
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 70px;
}
QPushButton:hover { background-color: ACCENT_HOVER; }
QPushButton:pressed { background-color: ACCENT_PRESSED; }

/* Secundario — btn.setObjectName("secondary") */
QPushButton#secondary {
    background-color: BG_INPUT;
    color: TEXT_PRIMARY;
    border: 1.5px solid BORDER;
    font-weight: 400;
}

/* Plano — btn.setObjectName("flat") */
QPushButton#flat {
    background: transparent;
    color: TEXT_SECONDARY;
    border: none;
    padding: 4px 8px;
    min-width: 0;
    font-weight: 400;
}

/* Peligro — btn.setObjectName("danger") */
QPushButton#danger {
    background-color: DANGER;
    color: TEXT_ON_ACCENT;
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
}
```

### 2.2 Inputs

```css
QLineEdit {
    background-color: BG_INPUT;
    color: TEXT_PRIMARY;
    border: 1.5px solid BORDER;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: ACCENT_LIGHT;
}
QLineEdit:focus {
    border-color: BORDER_FOCUS;
    background-color: BG_SURFACE;
}
```

### 2.3 Chat Burbujas (estilo manga)

**Usuario:**
```css
background: ACCENT_LIGHT;
color: TEXT_PRIMARY;
border-radius: 12px 12px 4px 12px;
padding: 8px 14px;
text-align: right;
```

**Asistente:**
```css
background: BG_SURFACE;
color: TEXT_PRIMARY;
border: 1px solid BORDER;
border-radius: 12px 12px 12px 4px;
padding: 8px 14px;
text-align: left;
```

**Sistema:**
```css
background: BG_SYSTEM_MSG;
color: TEXT_SECONDARY;
border-radius: 8px;
padding: 4px 14px;
text-align: center;
font-size: 11px;
```

### 2.4 Diálogos

**Mínimo:** `500 x 360 px`
**Estilo:** `DIALOG_STYLE` (fondo `BG_SURFACE`)

**Botones:**
- Acción primaria (Guardar/Añadir) → Sin objectName
- Cancelar/Cerrar → `objectName="secondary"`
- Eliminar → `objectName="danger"`

---

## 3. Componentes Especiales

### 3.1 Speech Bubble (Manga/Comic)

- **Fondo:** Blanco (`#FFFFFF`)
- **Borde:** Negro grueso (`#1E1E30`, `2.5px`)
- **Texto:** Bold, `13px`, sans-serif
- **Cola:** `20px` ancho, `13px` alto

### 3.2 Overlay Menu Contextual

```css
QMenu {
    background-color: BG_SURFACE;
    color: TEXT_PRIMARY;
    border: 2px solid TEXT_PRIMARY;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item:selected {
    background-color: ACCENT_LIGHT;
    color: ACCENT_PRESSED;
    font-weight: 600;
}
```

### 3.3 Inline Input (Overlay)

```css
QLineEdit {
    background-color: BG_SURFACE;
    color: TEXT_PRIMARY;
    border: 2.5px solid TEXT_PRIMARY;
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit:focus {
    border-color: BORDER_FOCUS;
}
```

---

## 4. Scrollbars (Minimalista)

```css
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: BORDER;
    border-radius: 3px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: TEXT_MUTED;
}
```

---

## 5. Reglas Generales

1. **Sin código hex en otros archivos** — usar constantes desde `styles.py`
2. **Todos los diálogos** → aplicar `DIALOG_STYLE`
3. **Centrar diálogos** en ventana padre en `showEvent`
4. **Manga bubble** → fondo blanco, borde negro grueso, texto bold
5. **Status bar** → compacta con emojis: `❤ ⚡ ✦ ☁ 🔔/🔕`
6. **Menú contextual overlay** → borde negro redondeado