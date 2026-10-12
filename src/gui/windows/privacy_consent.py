"""Dialogo de consentimiento de privacidad.

Se muestra una sola vez (la primera ejecucion) para informar de que TomoDesk
puede leer el titulo de la ventana activa. Sigue el sistema de ``Design.md``:
estilos de dialogo compartidos y centrado sobre la ventana padre en
``showEvent`` (seccion 5.3).

Todos los textos salen de ``i18n``; los ``_FALLBACK_*`` solo se usan si no hay
gestor de idiomas o si la clave no existe en ningun locale.
"""

import logging

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from src.gui.utils import force_taskbar_entry

logger = logging.getLogger(__name__)

_FALLBACK_TITLE = "Privacy"
_FALLBACK_BODY = (
    "TomoDesk can monitor the title of your active window to make contextual comments. "
    "Window titles may contain sensitive information (file names, URLs). This data is "
    "stored locally and may be sent to your LLM. Do you accept?"
)
_FALLBACK_ACCEPT = "Accept"
_FALLBACK_DECLINE = "Decline"


class PrivacyConsentDialog(QDialog):
    """Pregunta al usuario si acepta monitorizar el titulo de la ventana activa.

    La decision se toma por el codigo de retorno (``QDialog.Accepted`` /
    ``QDialog.Rejected``); ``result_value`` se mantiene sincronizado para quien
    prefiera consultarlo antes de que el dialogo se destruya.
    """

    def __init__(self, parent=None, i18n=None, styles=None):
        super().__init__(parent)
        self.i18n = i18n
        self.result_value: bool = False

        if styles is None:
            from src.gui.styles.styles import get_style_set
            styles = get_style_set("light")
        self.setStyleSheet(styles["dialog"])
        self.setWindowTitle(self._t("privacy.consent_title", _FALLBACK_TITLE))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        body = QLabel(self._t("privacy.consent_body", _FALLBACK_BODY))
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QHBoxLayout()
        self.accept_btn = QPushButton(self._t("privacy.accept", _FALLBACK_ACCEPT))
        # Primario: sin objectName (Design.md §2.1).
        self.accept_btn.clicked.connect(self._on_accept)
        buttons.addWidget(self.accept_btn)

        self.decline_btn = QPushButton(self._t("privacy.decline", _FALLBACK_DECLINE))
        self.decline_btn.setObjectName("secondary")
        self.decline_btn.clicked.connect(self._on_decline)
        buttons.addWidget(self.decline_btn)

        layout.addLayout(buttons)

        # La decisión se recorre en el orden visual: aceptar y luego declinar.
        QWidget.setTabOrder(self.accept_btn, self.decline_btn)
        force_taskbar_entry(self)

    def _t(self, key: str, fallback: str) -> str:
        """Traduce ``key`` y cae en ``fallback`` si la clave no existe.

        ``I18nManager.t`` devuelve la propia clave cuando no la encuentra, asi
        que se compara el resultado para no pintar ``privacy.consent_body`` en
        crudo.
        """
        if self.i18n is not None:
            text = self.i18n.t(key)
            if text != key:
                return text
        return fallback

    def showEvent(self, event) -> None:
        """Centra el dialogo sobre su padre (``Design.md`` §5.3)."""
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is None:
            return
        p = parent.geometry()
        self.move(
            p.x() + (p.width() - self.width()) // 2,
            p.y() + (p.height() - self.height()) // 2,
        )

    def _on_accept(self) -> None:
        self.result_value = True
        self.accept()

    def _on_decline(self) -> None:
        self.result_value = False
        self.reject()
