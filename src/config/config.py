import logging
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import yaml

from src.config.credentials import CredentialManager
from src.config.paths import (
    default_config_path,
    resource_dir,
    user_config_dir,
)
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
        "llama_cpp": {
            "model_path": "data/models/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "n_ctx": 4096,
            "model_repo": "bartowski/Llama-3.2-1B-Instruct-GGUF",
            "model_file": "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        },
    },
    "personality": {
        "name": "Tomo",
        "traits": "friendly, curious, helpful",
    },
    "modes": {
        "comment_probability": 0.1,
        "max_comments_per_hour": 2,
        "proactive_comments": False,
        "proactive_cooldown_seconds": 1800,
    },
    "context": {
        "directory": "data/context_packs",
    },
    "setup": {
        "completed": False,
    },
    "window_sitting": {
        "enabled": True,
        "target": "active_window",
        "transition_speed": 0.5,
        "fallback_position": "bottom-right",
        "maximized_behavior": 1,
        "minimized_behavior": 0,
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


_LEGACY_MODEL_REPO = "ggml-org/llama-3.2-1B-Instruct-GGUF"


def _migrate_llama_cpp_default(config: dict) -> bool:
    """Migra el repo ggml-org (gated en HuggingFace) al espejo publico.

    Solo actua si el usuario heredo el valor por defecto antiguo; una config
    personalizada (repo distinto) no se toca. Devuelve True si cambio algo.
    """
    llm = config.get("llm")
    if not isinstance(llm, dict):
        return False
    llama_cpp = llm.get("llama_cpp")
    if not isinstance(llama_cpp, dict) or not llama_cpp.get("model_repo"):
        return False
    if llama_cpp["model_repo"] != _LEGACY_MODEL_REPO:
        return False
    defaults = _NESTED_DEFAULTS["llm"]["llama_cpp"]
    llama_cpp["model_repo"] = defaults["model_repo"]
    llama_cpp["model_file"] = defaults["model_file"]
    llama_cpp["model_path"] = defaults["model_path"]
    logger.info("Migrado model_repo legacy (%s) al espejo %s",
                _LEGACY_MODEL_REPO, defaults["model_repo"])
    return True


def _strip_sensitive(config: dict) -> dict:
    safe = dict(config)
    llm = safe.get("llm")
    if isinstance(llm, dict):
        safe["llm"] = {k: v for k, v in llm.items() if k != "api_key"}
    return safe


def is_setup_completed(config: dict) -> bool:
    """True si el wizard de primera ejecucion ya se completo (o se omitio)."""
    setup = config.get("setup")
    if not isinstance(setup, dict):
        return False
    return bool(setup.get("completed", False))


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
    path.parent.mkdir(parents=True, exist_ok=True)
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

    env_path = user_config_dir() / ".env"
    load_dotenv(dotenv_path=env_path)
    if env_path.exists():
        secure_file(env_path)

    if config_path is None:
        config_path = default_config_path()

    bootstrapped = False
    if not config_path.exists():
        example = config_path.with_name("config.example.yaml")
        if not example.exists():
            example = resource_dir() / "config.example.yaml"
        if example.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(example, config_path)
            secure_file(config_path)
            bootstrapped = True
            logger.info(
                "config.yaml not found; bootstrapped from %s", example
            )
        else:
            raise FileNotFoundError(
                f"Configuration file not found at {config_path} "
                f"and no {example.name} available to bootstrap from. "
                "Ensure config.yaml (or config.example.yaml) is available."
            )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    secure_file(config_path)

    had_setup = isinstance(config.get("setup"), dict)
    _apply_nested_defaults(config)
    _CONFIG_PATH = config_path.resolve()

    # Migracion: una config preexistente (pre-1.4.0) sin seccion `setup` ya fue
    # configurada a mano; no volver a mostrar el asistente de primera ejecucion.
    migrated_setup = False
    if not bootstrapped and not had_setup:
        config["setup"]["completed"] = True
        migrated_setup = True

    if _migrate_llama_cpp_default(config) or migrated_setup:
        save_config(config, _CONFIG_PATH)

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
    return default_config_path().resolve()
