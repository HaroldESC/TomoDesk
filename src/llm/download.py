"""Descarga del modelo GGUF (llama.cpp) desde HuggingFace.

La descarga es explicita (comando ``/model download`` o boton en Ajustes), no
automatica. Usa ``urllib.request`` de la stdlib para no anadir dependencias y
escribe a un archivo ``.part`` que se renombra al terminar, de modo que una
descarga interrumpida no corrompe el destino.

Nota de licencia: el modelo por defecto (Meta Llama 3.2) se distribuye bajo la
Licencia de Comunidad Llama (https://llama.com/license/), distinta de la MIT del
repositorio. Consulta su licencia antes de redistribuirlo.
"""

import logging
import urllib.request
from pathlib import Path
from typing import Callable

from src.config import paths

logger = logging.getLogger(__name__)

# (repo, filename) del GGUF Q4_K_M de llama3.2:1b (~800MB). Se hostea en
# HuggingFace y NO se sube a Git (licencia de Comunidad Llama).
DEFAULT_MODEL_REPO = "ggml-org/llama-3.2-1B-Instruct-GGUF"
DEFAULT_MODEL_FILE = "llama-3.2-1B-Instruct-Q4_K_M.gguf"

# Perfil de un modelo valido para python-llama-cpp (placeholder doc).
MODEL_PROFILE = "llama3.2-1B Instruct (Q4_K_M)"


def model_dir() -> Path:
    """Directorio de modelos del usuario (creado por ensure_user_dirs)."""
    return paths.user_data_dir() / "data" / "models"


def default_model_path() -> Path:
    """Ruta por defecto del GGUF dentro de data/models/."""
    return model_dir() / DEFAULT_MODEL_FILE


def model_url_from_config(config: dict) -> str:
    """URL HuggingFace del modelo segun config (o la por defecto)."""
    llm = config.get("llm", {})
    llm_cpp = llm.get("llama_cpp", {})
    repo = llm_cpp.get("model_repo", DEFAULT_MODEL_REPO)
    filename = llm_cpp.get("model_file", DEFAULT_MODEL_FILE)
    return f"https://huggingface.co/{repo}/resolve/main/{filename}"


def model_path_from_config(config: dict) -> Path:
    """Ruta absoluta del .gguf segun config (relativa -> user data)."""
    llm = config.get("llm", {})
    llm_cpp = llm.get("llama_cpp", {})
    raw = llm_cpp.get("model_path") or str(default_model_path())
    path = Path(raw)
    if path.is_absolute():
        return path
    return paths.user_data_dir() / path


def model_exists(config: dict) -> bool:
    return model_path_from_config(config).exists()


def download_file(
    url: str,
    dest: Path,
    progress: Callable[[int, int], None] | None = None,
    chunk_size: int = 1024 * 1024,
    *,
    timeout: int = 30,
) -> Path:
    """Descarga ``url`` a ``dest`` con callback de progreso (bytes, total).

    Total es -1 si el servidor no reporta Content-Length.
    ``timeout`` es el timeout de conexion/lectura a nivel de socket en
    segundos de cada operacion de ``urlopen``.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "TomoDesk/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as f:
        total = int(resp.headers.get("Content-Length") or -1)
        downloaded = 0
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress:
                progress(downloaded, total)
    part.replace(dest)
    logger.info("Modelo descargado en %s (%s bytes)", dest, downloaded)
    return dest


def download_model(
    config: dict,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Descarga el GGUF configurado a su ruta destino."""
    url = model_url_from_config(config)
    dest = model_path_from_config(config)
    if dest.exists():
        logger.info("El modelo ya existe en %s", dest)
        return dest
    logger.info("Descargando modelo desde %s", url)
    return download_file(url, dest, progress)
