from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QWidget

from src.gui.windows.privacy_consent import PrivacyConsentDialog


def test_dialog_is_qdialog(qapp, mock_i18n):
    dialog = PrivacyConsentDialog(i18n=mock_i18n)
    try:
        assert isinstance(dialog, QDialog)
    finally:
        dialog.close()


def test_accept_sets_result(qapp, mock_i18n):
    dialog = PrivacyConsentDialog(i18n=mock_i18n)
    accept_btn = dialog.findChild(QPushButton, "primary")
    assert accept_btn is not None
    accept_btn.click()
    assert dialog.result_value is True
    assert dialog.result() == QDialog.Accepted
    dialog.close()


def test_decline_sets_result(qapp, mock_i18n):
    dialog = PrivacyConsentDialog(i18n=mock_i18n)
    decline_btn = dialog.findChild(QPushButton, "secondary")
    assert decline_btn is not None
    decline_btn.click()
    assert dialog.result_value is False
    assert dialog.result() == QDialog.Rejected
    dialog.close()


def test_i18n_used(qapp, mock_i18n):
    dialog = PrivacyConsentDialog(i18n=mock_i18n)
    try:
        mock_i18n.t.assert_any_call("privacy.consent_title")
    finally:
        dialog.close()


class TestTranslateHelper:
    """Los textos nunca deben mostrarse como el nombre de la clave."""

    def test_missing_key_falls_back_to_readable_text(self, qapp, mock_i18n):
        # ``mock_i18n.t`` devuelve la propia clave cuando no la encuentra.
        dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            assert dialog.windowTitle() == "Privacy"
            body = dialog.findChild(QLabel)
            assert "privacy.consent_body" not in body.text()
            assert "TomoDesk can monitor" in body.text()
        finally:
            dialog.close()

    def test_existing_key_uses_translation(self, qapp, mock_i18n):
        mock_i18n.t = MagicMock(return_value="Privacidad")
        dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            assert dialog.windowTitle() == "Privacidad"
        finally:
            dialog.close()

    def test_without_i18n_uses_fallbacks(self, qapp):
        dialog = PrivacyConsentDialog()
        try:
            assert dialog.windowTitle() == "Privacy"
        finally:
            dialog.close()


class TestStyles:
    """El dialogo debe respetar el tema de la ventana que lo abre."""

    def test_styles_argument_is_applied(self, qapp, mock_i18n):
        styles = {"dialog": "QDialog { background-color: #123456; }"}
        dialog = PrivacyConsentDialog(i18n=mock_i18n, styles=styles)
        try:
            assert dialog.styleSheet() == styles["dialog"]
        finally:
            dialog.close()

    def test_without_styles_falls_back_to_light(self, qapp, mock_i18n):
        from src.gui.styles.styles import get_style_set

        dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            assert dialog.styleSheet() == get_style_set("light")["dialog"]
        finally:
            dialog.close()


class TestTaskbarEntry:
    """``force_taskbar_entry`` nunca debe romper la construccion."""

    def _adapter(self, taskbar_entry=True):
        adapter = MagicMock()
        adapter.capabilities.taskbar_entry = taskbar_entry
        adapter.force_taskbar_entry.return_value = True
        return adapter

    def test_asks_platform_for_taskbar_entry(self, qapp, mock_i18n):
        adapter = self._adapter()
        with patch("src.gui.utils.get_platform", return_value=adapter):
            dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            adapter.force_taskbar_entry.assert_called_once()
        finally:
            dialog.close()

    def test_unsupported_platform_is_noop(self, qapp, mock_i18n):
        adapter = self._adapter(taskbar_entry=False)
        with patch("src.gui.utils.get_platform", return_value=adapter):
            dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            adapter.force_taskbar_entry.assert_not_called()
            assert isinstance(dialog, QDialog)
        finally:
            dialog.close()

    def test_platform_failure_does_not_break_dialog(self, qapp, mock_i18n):
        adapter = self._adapter()
        adapter.force_taskbar_entry.side_effect = OSError("boom")
        with patch("src.gui.utils.get_platform", return_value=adapter):
            dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            assert isinstance(dialog, QDialog)
            assert dialog.windowTitle() == "Privacy"
        finally:
            dialog.close()


class TestCentering:
    """``Design.md`` §5.3: los dialogos se centran sobre su padre."""

    def test_centers_over_parent(self, qapp, mock_i18n):
        parent = QWidget()
        parent.setGeometry(220, 160, 800, 600)
        dialog = PrivacyConsentDialog(parent=parent, i18n=mock_i18n)
        parent.show()
        try:
            dialog.show()
            qapp.processEvents()
            p = parent.geometry()
            assert dialog.pos().x() == p.x() + (p.width() - dialog.width()) // 2
            assert dialog.pos().y() == p.y() + (p.height() - dialog.height()) // 2
        finally:
            dialog.close()
            parent.close()

    def test_without_parent_does_not_move(self, qapp, mock_i18n):
        dialog = PrivacyConsentDialog(i18n=mock_i18n)
        try:
            dialog.show()
            qapp.processEvents()
            assert dialog.isVisible()
        finally:
            dialog.close()