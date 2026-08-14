import hashlib
import logging
import os
import threading
import time
os.environ["POSTHOG_DISABLED"] = "1"
os.environ["CHROMADB_TELEMETRY_DISABLED"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logger = logging.getLogger(__name__)

logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

from pathlib import Path
from typing import Any, List

import chromadb
from chromadb import Collection
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


_DEFAULT_EMBEDDING_CACHE_SIZE = 1000


class _EmbeddingCache:
    """LRU cache for computed embeddings.

    Thread-safe. Evicts least recently used entries when max size is reached.
    """

    def __init__(self, max_size: int = _DEFAULT_EMBEDDING_CACHE_SIZE):
        self._max_size = max_size
        self._cache: dict[str, List[float]] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()

    def _make_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> List[float] | None:
        key = self._make_key(text)
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
                self._order.append(key)
                return self._cache[key]
        return None

    def put(self, text: str, embedding: List[float]) -> None:
        key = self._make_key(text)
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
            elif len(self._cache) >= self._max_size:
                oldest = self._order.pop(0)
                del self._cache[oldest]
            self._cache[key] = embedding
            self._order.append(key)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._order.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
            }


class _SentenceTransformerEmbedding:
    def __init__(self, model_name: str, cache_size: int = _DEFAULT_EMBEDDING_CACHE_SIZE):
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._cache = _EmbeddingCache(max_size=cache_size)

    def __call__(self, input: List[str]) -> List[List[float]]:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = SentenceTransformer(self._model_name)

        results: List[List[float] | None] = [None] * len(input)
        to_compute: List[int] = []

        for i, text in enumerate(input):
            cached = self._cache.get(text)
            if cached is not None:
                results[i] = cached
            else:
                to_compute.append(i)

        if to_compute:
            texts_to_encode = [input[i] for i in to_compute]
            embeddings = self._model.encode(
                texts_to_encode, normalize_embeddings=True
            ).tolist()
            for idx, emb in zip(to_compute, embeddings):
                results[idx] = emb
                self._cache.put(input[idx], emb)

        return results

    def ensure_loaded(self):
        if self._model is None:
            self.__call__([""])

    def get_cache_stats(self) -> dict:
        return self._cache.get_stats()

    def clear_cache(self) -> None:
        self._cache.clear()


_COLLECTION_NAMES = [
    "personality",
    "memories",
    "context_rules",
    "episodic_memory",
    "notes_index",
]


_DEFAULT_QUERY_CACHE_SIZE = 100
_DEFAULT_QUERY_CACHE_TTL = 300  # 5 minutes


class _QueryCache:
    """TTL cache for ChromaDB query results.

    Thread-safe. Clears stale entries lazily on access.
    """

    def __init__(self, max_size: int = _DEFAULT_QUERY_CACHE_SIZE, ttl: float = _DEFAULT_QUERY_CACHE_TTL):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: dict[str, tuple[List[dict], float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _make_key(collection_name: str, query_text: str, n_results: int) -> str:
        return f"{collection_name}:::{hashlib.sha256(query_text.encode('utf-8')).hexdigest()}:::{n_results}"

    def get(self, collection_name: str, query_text: str, n_results: int) -> List[dict] | None:
        key = self._make_key(collection_name, query_text, n_results)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            result, timestamp = entry
            if time.time() - timestamp >= self._ttl:
                del self._cache[key]
                return None
            return result

    def put(self, collection_name: str, query_text: str, n_results: int, result: List[dict]) -> None:
        key = self._make_key(collection_name, query_text, n_results)
        with self._lock:
            if key not in self._cache and len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (result, time.time())

    def invalidate_all(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "ttl_seconds": self._ttl,
            }


class ChromaManager:
    def __init__(self, persist_path: str | Path, embedding_model: str):
        self._persist_path = Path(persist_path).resolve()
        self._embedding_model_name = embedding_model
        self._client: chromadb.PersistentClient | None = None
        self._embedding_function: _SentenceTransformerEmbedding | None = None
        self._collections: dict[str, Collection] = {}
        self._query_cache = _QueryCache()

    @staticmethod
    def _suppress_telemetry():
        pass

    def initialize(self) -> None:
        try:
            self._suppress_telemetry()
            self._persist_path.mkdir(parents=True, exist_ok=True)
            self._embedding_function = _SentenceTransformerEmbedding(
                self._embedding_model_name
            )
            self._client = chromadb.PersistentClient(
                path=str(self._persist_path),
                settings=Settings(anonymized_telemetry=False),
            )
            for name in _COLLECTION_NAMES:
                self._collections[name] = self._client.get_or_create_collection(
                    name=name,
                    embedding_function=self._embedding_function,
                )
        except Exception:
            logger.exception("Failed to initialize ChromaDB")

    def add_to_collection(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[dict],
        ids: List[str],
    ) -> None:
        try:
            col = self._collections[collection_name]
            col.add(documents=documents, metadatas=metadatas, ids=ids)
            self._query_cache.invalidate_all()
        except Exception:
            logger.exception("ChromaDB add_to_collection failed")

    def query_collection(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
    ) -> List[dict[str, Any]]:
        cached = self._query_cache.get(collection_name, query_text, n_results)
        if cached is not None:
            return cached

        try:
            col = self._collections[collection_name]
            results = col.query(query_texts=[query_text], n_results=n_results)
            items = []
            if not results["ids"]:
                return items
            ids_list = results["ids"][0]
            dist_list = results["distances"][0] if results["distances"] else []
            docs_list = results["documents"][0] if results["documents"] else []
            meta_list = results["metadatas"][0] if results["metadatas"] else []

            for i in range(len(ids_list)):
                items.append(
                    {
                        "id": ids_list[i],
                        "document": docs_list[i] if i < len(docs_list) else "",
                        "metadata": meta_list[i] if i < len(meta_list) else {},
                        "distance": dist_list[i] if i < len(dist_list) else 0.0,
                    }
                )
            self._query_cache.put(collection_name, query_text, n_results, items)
            return items
        except Exception:
            logger.exception("ChromaDB query_collection failed")
            return []

    def get_all(
        self, collection_name: str
    ) -> List[dict[str, Any]]:
        try:
            col = self._collections[collection_name]
            results = col.get()
            items = []
            if not results["ids"]:
                return items
            for i in range(len(results["ids"])):
                items.append(
                    {
                        "id": results["ids"][i],
                        "document": (
                            results["documents"][i] if results["documents"] else ""
                        ),
                        "metadata": (
                            results["metadatas"][i] if results["metadatas"] else {}
                        ),
                    }
                )
            return items
        except Exception:
            logger.exception("ChromaDB get_all failed")
            return []

    def delete_from_collection(self, collection_name: str, ids: List[str]) -> None:
        try:
            col = self._collections[collection_name]
            col.delete(ids=ids)
            self._query_cache.invalidate_all()
        except Exception:
            logger.exception("ChromaDB delete_from_collection failed")

    def update_in_collection(
        self,
        collection_name: str,
        ids: List[str],
        documents: List[str] | None = None,
        metadatas: List[dict] | None = None,
    ) -> None:
        try:
            col = self._collections[collection_name]
            col.update(ids=ids, documents=documents, metadatas=metadatas)
            self._query_cache.invalidate_all()
        except Exception:
            logger.exception("ChromaDB update_in_collection failed")

    def count(self, collection_name: str) -> int:
        try:
            col = self._collections[collection_name]
            return col.count()
        except Exception:
            logger.exception("ChromaDB count failed")
            return 0