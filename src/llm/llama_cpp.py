"""Proveedor LLM local basado en ``llama-cpp-python`` (dependencia opcional).

La libreria ``llama-cpp-python`` (wheel CPU) NO es una dependencia obligatoria
de TomoDesk; solo se cargan de forma perezosa dentro de este modulo. Si no esta
instalada, ``is_available()`` devuelve ``False`` y ``generate``/``generate_stream``
lanzan ``LLMError`` con un mensaje claro. Esto mantiene el binario base ligero;
los usuarios que quieran el modelo embebido instalan la wheel o usan el asset
"full".
"""

import logging
from pathlib import Path
from typing import Dict, Generator, List

from src.llm.llm import LLMError, LLMProvider

logger = logging.getLogger(__name__)


class LlamaCppProvider(LLMProvider):
    """Inference local Q4_K_M via llama.cpp (llama-cpp-python, opcional)."""

    def __init__(
        self,
        model_path: str | Path,
        n_ctx: int = 4096,
        max_requests_per_minute: int = 60,
        **model_kwargs,
    ):
        super().__init__(max_requests_per_minute)
        self.model_path = Path(model_path)
        self.n_ctx = n_ctx
        self._model_kwargs = dict(model_kwargs)  # p.ej. n_threads, verbose
        self._llm = None
        self._import_error: Exception | None = None

    @property
    def model(self) -> str:
        """Nombre del archivo de modelo (etiqueta visible en la UI)."""
        return self.model_path.name

    def _load(self):
        if self._llm is not None or self._import_error is not None:
            return
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            self._import_error = exc
            logger.error(
                "llama-cpp-python no esta instalado. Instala la wheel "
                "CPU (pip install llama-cpp-python) o usa el asset 'full'."
            )
            return
        if not self.model_path.exists():
            logger.error("Modelo GGUF no encontrado: %s", self.model_path)
            return
        self._llm = Llama(
            model_path=str(self.model_path),
            n_ctx=int(self.n_ctx),
            verbose=False,
            **self._model_kwargs,
        )

    def is_available(self) -> bool:
        self._load()
        return self._llm is not None

    def generate(self, messages: List[Dict[str, str]]) -> str:
        self._throttle()
        self._load()
        if self._llm is None:
            raise LLMError(self._unavailable_message())
        try:
            response = self._llm.create_chat_completion(
                messages=messages, stream=False
            )
            return response["choices"][0]["message"]["content"] or ""
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("Error generando con llama_cpp")
            raise LLMError(f"llama_cpp generation failed: {exc}")

    def generate_stream(
        self, messages: List[Dict[str, str]]
    ) -> Generator[str, None, None]:
        self._throttle()
        self._load()
        if self._llm is None:
            raise LLMError(self._unavailable_message())
        try:
            stream = self._llm.create_chat_completion(
                messages=messages, stream=True
            )
            for chunk in stream:
                delta = chunk["choices"][0]["delta"]
                content = delta.get("content", "")
                if content:
                    yield content
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("Error en streaming con llama_cpp")
            raise LLMError(f"llama_cpp streaming failed: {exc}")

    def _unavailable_message(self) -> str:
        if self._import_error is not None:
            return (
                "llama-cpp-python no esta instalado. Instala la wheel CPU "
                "(pip install llama-cpp-python) o usa el asset 'full'."
            )
        return (
            f"Modelo GGUF no encontrado en {self.model_path}. "
            "Descargalo con el comando /model download o desde Ajustes."
        )
