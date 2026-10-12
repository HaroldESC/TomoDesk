"""Iconos de la barra de estado.

``Design.md`` §5.5 pide una barra compacta con emojis, pero enseniarlos
siempre puede distraer: su uso se controla con ``ui.status_icons``
(desactivado por defecto).

Este modulo es el unico sitio de la GUI donde viven esos caracteres. Fuera
de aqui se consumen por nombre (``status_icon("radiant")``), nunca
escritos a mano, y una clave desconocida devuelve cadena vacia para que un
estado nuevo no rompa la barra.
"""

# Estado emocional del asistente (una clave por rama de _update_status_message).
ICON_LISTENING = "\u2764\ufe0f"
ICON_CURIOUS = "\u2726"
ICON_RADIANT = "\u26a1"
ICON_TIRED = "\u2601"
ICON_DISTANT = "\U0001f515"
ICON_SLEEPING = "\U0001f4a4"

# Modos de comportamiento.
ICON_PROACTIVE = "\U0001f514"
ICON_DND = "\U0001f515"
ICON_FOCUS = "\U0001f3af"

#: Icono de cada estado emocional, con las mismas claves que usa el estado.
STATUS_ICONS: dict[str, str] = {
    "listening": ICON_LISTENING,
    "curious": ICON_CURIOUS,
    "radiant": ICON_RADIANT,
    "tired": ICON_TIRED,
    "distant": ICON_DISTANT,
    "sleeping": ICON_SLEEPING,
}

#: Icono de cada modo de comportamiento.
MODE_ICONS: dict[str, str] = {
    "proactive": ICON_PROACTIVE,
    "dnd": ICON_DND,
    "focus": ICON_FOCUS,
}

#: Familias de iconos recuperables con :func:`icon`.
_ICON_SETS: dict[str, dict[str, str]] = {
    "status": STATUS_ICONS,
    "mode": MODE_ICONS,
}


def status_icon(key: str) -> str:
    """Icono de un estado emocional del asistente.

    :param key: clave del estado (``"listening"``, ``"radiant"``...).
    :return: el emoji, o una cadena vacia si el estado no tiene icono.
    """
    return STATUS_ICONS.get(key, "")


def icon(prefix: str, key: str) -> str:
    """Icono de una familia concreta (``"status"`` o ``"mode"``).

    :param prefix: nombre de la familia de iconos.
    :param key: clave del icono dentro de esa familia.
    :return: el emoji, o una cadena vacia si la familia o la clave no
        existen, para que un valor nuevo nunca rompa la barra de estado.
    """
    return _ICON_SETS.get(prefix, {}).get(key, "")
