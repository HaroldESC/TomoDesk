"""Resolución de rutas: recursos embebidos vs. datos de usuario.

En desarrollo (modo fuente) ``resource_dir()``, ``user_data_dir()`` y
``user_config_dir()`` coinciden con la raíz del repositorio, por lo que el
comportamiento no cambia. En builds empaquetados (PyInstaller/AppImage) se
separan tres bases:

- ``resource_dir()``: recursos de solo lectura que viajan dentro del bundle
  (locales, sprites por defecto, packs embebidos, ejemplo de config).
- ``user_data_dir()``: datos escribibles del usuario (db, chroma, descargas).
- ``user_config_dir()``: ``config.yaml`` y ``.env``.

``config.yaml`` guarda rutas relativas (portables); ``resolve()`` las convierte
en rutas absolutas siguiendo la política de cada clave: relativas que apuntan a
recursos de solo lectura se resuelven contra ``resource_dir()`` y el resto
contra ``user_data_dir()``. Las rutas absolutas que el usuario escriba se
preservan tal cual.
"""

import os
import sys
from pathlib import Path

_APP_DIR_NAME_WIN = "TomoDesk"
_APP_DIR_NAME_POSIX = "tomodesk"

_RESOURCE = "resource"
_USER = "user"

# (clave, subclave) -> (base, default relativo)
_PATH_POLICY: dict[tuple[str, ...], tuple[str, str]] = {
    ("paths", "locales"): (_RESOURCE, "data/locales"),
    ("paths", "comments_yaml"): (_RESOURCE, "data/comments.yaml"),
    ("database", "sqlite_path"): (_USER, "data/tomodesk.db"),
    ("memory", "chroma_persist_path"): (_USER, "chroma_db"),
    ("personality_packs", "directory"): (_USER, "data/personality_packs"),
    ("context", "directory"): (_USER, "data/context_packs"),
    ("ui", "sprite", "custom_path"): (_USER, "data/sprites/custom"),
}


def is_frozen() -> bool:
    """True cuando la app corre empaquetada (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def resource_dir() -> Path:
    """Base de recursos de solo lectura (bundle en empaquetado)."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return _project_root()


def user_data_dir() -> Path:
    """Base de datos escribibles del usuario."""
    if not is_frozen():
        return _project_root()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME_WIN
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        return base / _APP_DIR_NAME_POSIX
    return _project_root()


def user_config_dir() -> Path:
    """Base de config.yaml y .env."""
    if not is_frozen():
        return _project_root()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME_WIN
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / _APP_DIR_NAME_POSIX
    return _project_root()


def default_config_path() -> Path:
    return user_config_dir() / "config.yaml"


def log_dir() -> Path:
    return user_data_dir() / "data"


def default_sprite_dir() -> Path:
    return resource_dir() / "data" / "sprites"


def bundled_defaults_dir(*rel: str) -> Path | None:
    """Directorio de defaults embebidos, o ``None`` en desarrollo.

    En modo fuente ``resource_dir()`` coincide con ``user_data_dir()``, por lo
    que escanear ambos duplicaría los packs; devolver ``None`` evita el doble
    escaneo sin cambiar el comportamiento actual.
    """
    if not is_frozen():
        return None
    return resource_dir().joinpath(*rel)


def _get_raw(config: dict, keys: tuple[str, ...]) -> str | None:
    node: object = config
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, str) and node.strip():
        return node.strip()
    return None


def resolve(config: dict, *keys: str) -> Path:
    """Resuelve una clave de config a una ruta absoluta según la política."""
    base_kind, default = _PATH_POLICY[keys]
    raw = _get_raw(config, keys) or default
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    base = resource_dir() if base_kind == _RESOURCE else user_data_dir()
    return base / candidate


def resolve_raw(raw: str, base: Path) -> Path:
    """Resuelve una cadena arbitraria: absoluta pasa, relativa se ancla a base."""
    candidate = Path(raw or "")
    if candidate.is_absolute():
        return candidate
    return base / candidate


def user_resolve(raw: str) -> Path:
    """Resuelve una cadena relativa contra la base de datos de usuario."""
    return resolve_raw(raw, user_data_dir())


def ensure_user_dirs() -> None:
    """Crea las carpetas de datos de usuario (no-op en desarrollo)."""
    user_data_dir().mkdir(parents=True, exist_ok=True)
    for rel in ("data", "data/models"):
        (user_data_dir() / rel).mkdir(parents=True, exist_ok=True)