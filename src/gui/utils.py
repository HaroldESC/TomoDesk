"""Shared helpers for GUI windows."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtWidgets import QMessageBox, QWidget

from src.platform import get_platform

logger = logging.getLogger(__name__)

#: Claves por defecto de los botones de :func:`confirm`.
CONFIRM_ACCEPT_KEY = "dialogs.confirm.accept"
CONFIRM_CANCEL_KEY = "dialogs.confirm.cancel"


def _translate(i18n: Any, key: str) -> str:
    """Traduce ``key`` sin propagar nunca una excepcion.

    Si el gestor de i18n no existe o falla (clave ausente, mock sin ``t``,
    error interno) se devuelve la propia clave: es preferible un boton con
    el nombre de la clave a un dialogo que revienta al abrirse.
    """
    if i18n is None or not key:
        return key or ""
    try:
        return str(i18n.t(key))
    except Exception:
        logger.debug("i18n lookup failed for %s", key, exc_info=True)
        return key


def confirm(
    parent: QWidget | None,
    i18n: Any,
    *,
    title_key: str,
    body_key: str,
    accept_key: str | None = None,
    cancel_key: str | None = None,
) -> bool:
    """Pregunta al usuario antes de una accion destructiva o de perder cambios.

    Construye el QMessageBox con addButton(..., ButtonRole) en vez del
    question() estatico porque PySide6 no permite recuperar los
    StandardButton traducidos. El boton de cancelar es el de defecto.
    Devuelve True solo si el usuario pulsa el boton de aceptar.

    Es deliberadamente a prueba de fallos: si falta una clave de traduccion
    se muestra la propia clave, y si el dialogo no se puede construir o
    ejecutar se devuelve False (nunca se lanza). Los textos no llevan
    marcadores ``{...}``, asi que no se aplica ``str.format``.
    """
    try:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_translate(i18n, title_key))
        box.setText(_translate(i18n, body_key))
        cancel = box.addButton(
            _translate(i18n, cancel_key or CONFIRM_CANCEL_KEY),
            QMessageBox.ButtonRole.RejectRole,
        )
        accept = box.addButton(
            _translate(i18n, accept_key or CONFIRM_ACCEPT_KEY),
            QMessageBox.ButtonRole.AcceptRole,
        )
        # Cancelar es la accion por defecto: nada se pierde sin querer.
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() is accept
    except Exception:
        logger.debug("confirm dialog failed", exc_info=True)
        return False


def force_taskbar_entry(widget: QWidget) -> bool:
    """Force the dialog to get its own taskbar entry (Windows).

    Asks the platform adapter to set WS_EX_APPWINDOW on the widget's native
    handle. The handle is created first via ``winId()`` so the adapter always
    receives a valid hwnd. Returns the adapter outcome and never raises.
    """
    try:
        adapter = get_platform()
        if not adapter.capabilities.taskbar_entry:
            return False
        widget.winId()
        hwnd = int(widget.winId())
        return bool(adapter.force_taskbar_entry(hwnd))
    except Exception:
        logger.debug("force_taskbar_entry failed", exc_info=True)
        return False
