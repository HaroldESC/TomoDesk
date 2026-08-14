import logging

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

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
    def __init__(self, i18n=None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.result_value: bool = False

        from src.gui.styles.styles import get_style_set
        self.setStyleSheet(get_style_set("light")["dialog"])
        self.setWindowTitle(self._t("privacy.consent_title", _FALLBACK_TITLE))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        body = QLabel(self._t("privacy.consent_body", _FALLBACK_BODY))
        body.setWordWrap(True)
        layout.addWidget(body)

        buttons = QHBoxLayout()
        accept_btn = QPushButton(self._t("privacy.accept", _FALLBACK_ACCEPT))
        accept_btn.setObjectName("primary")
        accept_btn.clicked.connect(self._on_accept)
        buttons.addWidget(accept_btn)

        decline_btn = QPushButton(self._t("privacy.decline", _FALLBACK_DECLINE))
        decline_btn.setObjectName("secondary")
        decline_btn.clicked.connect(self._on_decline)
        buttons.addWidget(decline_btn)

        layout.addLayout(buttons)

    def _t(self, key: str, fallback: str) -> str:
        if self.i18n is not None:
            return self.i18n.t(key)
        return fallback

    def _on_accept(self) -> None:
        self.result_value = True
        self.accept()

    def _on_decline(self) -> None:
        self.result_value = False
        self.reject()
