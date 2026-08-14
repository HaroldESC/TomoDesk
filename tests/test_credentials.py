import sys
from unittest.mock import MagicMock, patch

import pytest

from src.config.credentials import CredentialManager


class TestGetSecret:
    def test_returns_keyring_value(self):
        fake = MagicMock()
        fake.get_password.return_value = "k"
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.get_secret("llm_api_key") == "k"
        fake.get_password.assert_called_once_with("TomoDesk", "llm_api_key")

    def test_falls_back_to_env_var(self, monkeypatch):
        fake = MagicMock()
        fake.get_password.return_value = None
        monkeypatch.setenv("LLM_API_KEY", "env-key")
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.get_secret("llm_api_key") == "env-key"

    def test_returns_none_when_unavailable(self, monkeypatch):
        fake = MagicMock()
        fake.get_password.return_value = None
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.get_secret("llm_api_key") is None


class TestSetSecret:
    def test_stores_and_returns_true(self):
        fake = MagicMock()
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.set_secret("llm_api_key", "v") is True
        fake.set_password.assert_called_once_with("TomoDesk", "llm_api_key", "v")

    def test_returns_false_when_keyring_raises(self):
        fake = MagicMock()
        fake.set_password.side_effect = Exception("boom")
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.set_secret("llm_api_key", "v") is False


class TestDeleteSecret:
    def test_calls_delete_password(self):
        fake = MagicMock()
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            manager.delete_secret("llm_api_key")
        fake.delete_password.assert_called_once_with("TomoDesk", "llm_api_key")

    def test_does_not_raise_on_error(self):
        fake = MagicMock()
        fake.delete_password.side_effect = Exception("boom")
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            manager.delete_secret("llm_api_key")


class TestMigrateFromConfig:
    def test_stores_when_api_key_present_and_no_existing(self, monkeypatch):
        fake = MagicMock()
        fake.get_password.return_value = None
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        manager = CredentialManager()
        config = {"llm": {"api_key": "migrate-key"}}
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.migrate_from_config(config) is True
        fake.set_password.assert_called_once_with(
            "TomoDesk", "llm_api_key", "migrate-key"
        )

    def test_returns_false_when_secret_exists(self):
        fake = MagicMock()
        fake.get_password.return_value = "existing"
        manager = CredentialManager()
        config = {"llm": {"api_key": "migrate-key"}}
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.migrate_from_config(config) is False
        fake.set_password.assert_not_called()

    def test_returns_false_when_no_api_key(self):
        fake = MagicMock()
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.migrate_from_config({"llm": {}}) is False
        fake.set_password.assert_not_called()


class TestHasCredentials:
    def test_true_when_secret_available(self):
        fake = MagicMock()
        fake.get_password.return_value = "k"
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.has_credentials() is True

    def test_false_when_nothing_available(self, monkeypatch):
        fake = MagicMock()
        fake.get_password.return_value = None
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        manager = CredentialManager()
        with patch.dict(sys.modules, {"keyring": fake}):
            assert manager.has_credentials() is False
