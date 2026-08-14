import logging
import os

logger = logging.getLogger(__name__)


class CredentialManager:
    SERVICE_NAME = "TomoDesk"

    _ENV_MAP = {
        "llm_api_key": "LLM_API_KEY",
    }

    def get_secret(self, name: str) -> str | None:
        try:
            import keyring
            val = keyring.get_password(self.SERVICE_NAME, name)
            if val:
                return val
        except Exception:
            pass

        env_var = self._ENV_MAP.get(name)
        if env_var:
            val = os.environ.get(env_var)
            if val:
                return val

        return None

    def set_secret(self, name: str, value: str) -> bool:
        try:
            import keyring
            keyring.set_password(self.SERVICE_NAME, name, value)
            logger.debug("Credential '%s' stored in system keyring", name)
            return True
        except Exception as e:
            logger.warning("Failed to store '%s' in system keyring: %s", name, e)
            return False

    def delete_secret(self, name: str) -> None:
        try:
            import keyring
            keyring.delete_password(self.SERVICE_NAME, name)
        except Exception:
            pass

    def migrate_from_config(self, config: dict) -> bool:
        api_key = config.get("llm", {}).get("api_key")
        if not api_key:
            return False
        existing = self.get_secret("llm_api_key")
        if existing:
            return False
        return self.set_secret("llm_api_key", api_key)

    def has_credentials(self) -> bool:
        for name in self._ENV_MAP:
            if self.get_secret(name):
                return True
        return False
