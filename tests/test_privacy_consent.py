from PySide6.QtWidgets import QDialog, QPushButton

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
