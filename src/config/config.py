import logging
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import yaml

from src.config.credentials import CredentialManager
from src.config.secure_files import secure_file

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"llm", "memory", "personality", "modes", "database"}
_CONFIG_PATH: Path | None = None

_NESTED_DEFAULTS: dict[str, dict] = {
    "database": {
        "sqlite_path": "./data/tomodesk.db",
    },
    "memory": {
        "chroma_persist_path": "./chroma_db",
        "embedding_model": "all-MiniLM-L6-v2",
        "max_short_term_messages": 20,
    },
    "llm": {
        "provider": "ollama",
        "model": "llama3.2:1b",
        "endpoint": "http://localhost:11434",
        "timeout": 60,
        "max_requests_per_minute": 60,
    },
    "personality": {
        "name": "TomoDesk",
        "traits": "friendly, curious, helpful",
    },
}


def _apply_nested_defaults(config: dict) -> None:
    for section, defaults in _NESTED_DEFAULTS.items():
        target = config.setdefault(section, {})
        if not isinstance(target, dict):
            target = {}
            config[section] = target
        for key, value in defaults.items():
            target.setdefault(key, value)


def _get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _strip_sensitive(config: dict) -> dict:
    safe = dict(config)
    llm = safe.get("llm")
    if isinstance(llm, dict):
        safe["llm"] = {k: v for k, v in llm.items() if k != "api_key"}
    return safe


def validate_llm_endpoint(url: str) -> bool:
    """Return True if `url` is an http(s) endpoint with a non-empty host."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(
        parsed.hostname or parsed.netloc
    )


def save_config(config: dict, path: Path | None = None) -> None:
    if path is None:
        path = get_config_path()
    safe = _strip_sensitive(config)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.dump(safe, f, default_flow_style=False, allow_unicode=True)
    secure_file(tmp)
    tmp.replace(path)
    secure_file(path)
    logger.debug("Config saved to %s (secrets stripped)", path)


def load_config(config_path: Path | None = None) -> dict:
    global _CONFIG_PATH

    env_path = _get_project_root() / ".env"
    load_dotenv(dotenv_path=env_path)
    if env_path.exists():
        secure_file(env_path)

    if config_path is None:
        config_path = _get_project_root() / "config.yaml"

    if not config_path.exists():
        example = config_path.with_name("config.example.yaml")
        if example.exists():
            shutil.copy2(example, config_path)
            secure_file(config_path)
            logger.info(
                "config.yaml not found; bootstrapped from %s", example
            )
        else:
            raise FileNotFoundError(
                f"Configuration file not found at {config_path} "
                f"and no {example.name} available to bootstrap from. "
                "Ensure config.yaml exists at the project root."
            )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    secure_file(config_path)

    _apply_nested_defaults(config)
    _CONFIG_PATH = config_path.resolve()

    creds = CredentialManager()
    migrated = creds.migrate_from_config(config)

    if migrated:
        logger.info("Migrated legacy api_key from config to system keyring")
        config.get("llm", {}).pop("api_key", None)
        save_config(config, _CONFIG_PATH)
    else:
        api_key = os.environ.get("LLM_API_KEY") or config.get("llm", {}).get("api_key")
        if api_key:
            config.setdefault("llm", {})["api_key"] = api_key

    missing = _REQUIRED_KEYS - set(config.keys())
    if missing:
        raise KeyError(
            f"Missing required top-level key(s) in config: {', '.join(sorted(missing))}"
        )

    return config


def get_config_path() -> Path:
    global _CONFIG_PATH
    if _CONFIG_PATH is not None:
        return _CONFIG_PATH
    return Path("config.yaml").resolve()
