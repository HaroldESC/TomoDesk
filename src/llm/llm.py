import logging
from abc import ABC, abstractmethod
from typing import Dict, Generator, List

import ollama

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM provider fails to generate a response."""


class LLMProvider(ABC):
    def __init__(self, max_requests_per_minute: int = 60):
        from src.llm.rate_limit import RateLimiter

        self._rate_limiter = (
            RateLimiter(max_requests_per_minute)
            if max_requests_per_minute and max_requests_per_minute > 0
            else None
        )

    def _throttle(self) -> None:
        """Wait for rate-limit capacity before issuing a request."""
        if self._rate_limiter:
            self._rate_limiter.wait()

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]]) -> str:
        pass

    @abstractmethod
    def generate_stream(
        self, messages: List[Dict[str, str]]
    ) -> Generator[str, None, None]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        endpoint: str = "http://localhost:11434",
        max_requests_per_minute: int = 60,
    ):
        super().__init__(max_requests_per_minute)
        self.model = model
        self._endpoint = endpoint
        self._client = ollama.Client(host=endpoint)

    def generate(self, messages: List[Dict[str, str]]) -> str:
        self._throttle()
        try:
            response = self._client.chat(
                model=self.model, messages=messages, stream=False
            )
            return response["message"]["content"]
        except ollama.ResponseError:
            logger.error("Ollama ResponseError while generating")
            raise LLMError("Could not reach Ollama. Is it running?")
        except ConnectionError:
            logger.error("Connection refused to Ollama at %s", self._endpoint)
            raise LLMError(f"Connection refused. Is Ollama running at {self._endpoint}?")
        except Exception:
            logger.exception("Unexpected error during LLM generate")
            raise LLMError("Unexpected error during LLM generate. Check logs.")

    def generate_stream(
        self, messages: List[Dict[str, str]]
    ) -> Generator[str, None, None]:
        self._throttle()
        try:
            stream = self._client.chat(
                model=self.model, messages=messages, stream=True
            )
            for chunk in stream:
                yield chunk["message"]["content"]
        except ollama.ResponseError:
            logger.error("Ollama ResponseError during stream")
            raise LLMError("Could not reach Ollama. Is it running?")
        except ConnectionError:
            logger.error("Connection refused to Ollama during stream")
            raise LLMError(f"Connection refused. Is Ollama running at {self._endpoint}?")
        except Exception:
            logger.exception("Unexpected error during LLM stream")
            raise LLMError("Unexpected error during LLM stream. Check logs.")

    def is_available(self) -> bool:
        try:
            response = self._client.list()
            config_base = self.model.split(":")[0]
            for m in response.models:
                model_name = m.model.split(":")[0]
                if config_base == model_name:
                    return True
            return False
        except Exception:
            logger.warning("Failed to check Ollama availability", exc_info=True)
            return False


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        endpoint: str,
        api_key: str = None,
        max_requests_per_minute: int = 60,
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAICompatibleProvider. "
                "Install it with: pip install openai"
            )
        super().__init__(max_requests_per_minute)
        self.model = model
        base_url = endpoint.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
        )
        logger.info(f"OpenAICompatibleProvider initialized: {endpoint} (model: {model})")

    def generate(self, messages: List[Dict[str, str]]) -> str:
        self._throttle()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                timeout=60,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI-compatible provider error: {e}")
            raise LLMError(f"Could not reach the API. Check your endpoint. {e}")

    def generate_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        self._throttle()
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                timeout=60,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI-compatible streaming error: {e}")
            raise LLMError(f"Streaming error: {e}")

    def is_available(self) -> bool:
        try:
            models = self.client.models.list()
            model_ids = [m.id for m in models.data]
            return self.model in model_ids
        except Exception:
            return False


def create_provider(config: Dict, api_key: str | None = None) -> LLMProvider:
    llm_config = config["llm"]
    provider_type = llm_config["provider"]
    max_requests_per_minute = llm_config.get("max_requests_per_minute", 60)
    if provider_type == "ollama":
        return OllamaProvider(
            model=llm_config["model"],
            endpoint=llm_config["endpoint"],
            max_requests_per_minute=max_requests_per_minute,
        )
    elif provider_type == "openai_compatible":
        endpoint = llm_config["endpoint"]
        from src.config.config import validate_llm_endpoint

        if not validate_llm_endpoint(endpoint):
            raise ValueError(f"Invalid LLM endpoint: {endpoint}")
        return OpenAICompatibleProvider(
            model=llm_config["model"],
            endpoint=endpoint,
            api_key=api_key or "not-needed",
            max_requests_per_minute=max_requests_per_minute,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")
