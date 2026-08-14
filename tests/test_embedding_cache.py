import threading
import time

import pytest

from src.memory.chroma_manager import _EmbeddingCache, _SentenceTransformerEmbedding


class TestEmbeddingCache:
    def test_put_and_get(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("hello", [0.1, 0.2, 0.3])
        assert cache.get("hello") == [0.1, 0.2, 0.3]

    def test_get_missing(self):
        cache = _EmbeddingCache(max_size=10)
        assert cache.get("nonexistent") is None

    def test_get_after_clear(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("hello", [0.1, 0.2])
        cache.clear()
        assert cache.get("hello") is None

    def test_cache_hit_returns_same_list(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("hello", [0.1, 0.2, 0.3])
        result1 = cache.get("hello")
        result2 = cache.get("hello")
        assert result1 == result2
        assert result1 is result2

    def test_different_texts(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("hello", [0.1, 0.2])
        cache.put("world", [0.3, 0.4])
        assert cache.get("hello") == [0.1, 0.2]
        assert cache.get("world") == [0.3, 0.4]
        assert cache.size == 2

    def test_empty_cache_size(self):
        cache = _EmbeddingCache(max_size=10)
        assert cache.size == 0

    def test_size_after_puts(self):
        cache = _EmbeddingCache(max_size=10)
        for i in range(5):
            cache.put(f"key{i}", [float(i)])
        assert cache.size == 5

    def test_clear_resets_size(self):
        cache = _EmbeddingCache(max_size=10)
        for i in range(5):
            cache.put(f"key{i}", [float(i)])
        cache.clear()
        assert cache.size == 0

    def test_put_updates_existing_key(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("hello", [0.1, 0.2])
        cache.put("hello", [0.9, 0.9])
        assert cache.get("hello") == [0.9, 0.9]
        assert cache.size == 1

    def test_stats(self):
        cache = _EmbeddingCache(max_size=50)
        cache.put("a", [0.0])
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 50

    def test_stats_empty(self):
        cache = _EmbeddingCache(max_size=10)
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 10

    def test_clear_after_partial_fill(self):
        cache = _EmbeddingCache(max_size=5)
        cache.put("a", [0.0])
        cache.put("b", [0.1])
        cache.clear()
        cache.put("c", [0.2])
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") == [0.2]

    def test_many_puts_no_eviction(self):
        cache = _EmbeddingCache(max_size=100)
        for i in range(50):
            cache.put(f"key{i}", [float(i)])
        assert cache.size == 50
        for i in range(50):
            assert cache.get(f"key{i}") == [float(i)]

    def test_same_key_repeated_no_duplicate(self):
        cache = _EmbeddingCache(max_size=5)
        cache.put("same", [0.0])
        cache.put("same", [0.1])
        cache.put("same", [0.2])
        assert cache.size == 1


class TestEmbeddingCacheLRUEviction:
    def test_evicts_oldest_when_full(self):
        cache = _EmbeddingCache(max_size=3)
        cache.put("a", [0.0])
        cache.put("b", [0.1])
        cache.put("c", [0.2])
        cache.put("d", [0.3])
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None
        assert cache.get("d") is not None

    def test_eviction_keeps_correct_size(self):
        cache = _EmbeddingCache(max_size=3)
        for i in range(20):
            cache.put(f"key{i}", [float(i)])
        assert cache.size == 3

    def test_evicts_lru_after_access(self):
        cache = _EmbeddingCache(max_size=3)
        cache.put("a", [0.0])
        cache.put("b", [0.1])
        cache.put("c", [0.2])

        cache.get("a")
        cache.put("d", [0.3])

        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("c") is not None
        assert cache.get("d") is not None

    def test_evicts_lru_after_put_update(self):
        cache = _EmbeddingCache(max_size=3)
        cache.put("a", [0.0])
        cache.put("b", [0.1])
        cache.put("c", [0.2])

        cache.put("a", [0.5])
        cache.put("d", [0.3])

        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("c") is not None
        assert cache.get("d") is not None

    def test_evicts_multiple_times(self):
        cache = _EmbeddingCache(max_size=2)
        for i in range(10):
            cache.put(f"key{i}", [float(i)])
        assert cache.size == 2
        assert cache.get("key0") is None
        assert cache.get("key7") is None
        assert cache.get("key8") == [8.0]
        assert cache.get("key9") == [9.0]

    def test_single_entry(self):
        cache = _EmbeddingCache(max_size=1)
        cache.put("a", [0.0])
        assert cache.get("a") == [0.0]
        cache.put("b", [0.1])
        assert cache.get("a") is None
        assert cache.get("b") == [0.1]

    def test_no_eviction_before_full(self):
        cache = _EmbeddingCache(max_size=5)
        for i in range(5):
            cache.put(f"key{i}", [float(i)])
        assert cache.size == 5
        assert cache.get("key0") == [0.0]
        assert cache.get("key4") == [4.0]

    def test_eviction_preserves_remaining(self):
        cache = _EmbeddingCache(max_size=3)
        for i in range(3):
            cache.put(f"key{i}", [float(i)])
        cache.get("key0")
        cache.get("key1")
        cache.put("key_new", [99.0])
        assert cache.get("key2") is None
        assert cache.get("key0") == [0.0]
        assert cache.get("key1") == [1.0]
        assert cache.get("key_new") == [99.0]


class TestEmbeddingCacheEdgeCases:
    def test_long_text(self):
        cache = _EmbeddingCache(max_size=10)
        long_text = "a" * 10000
        cache.put(long_text, [0.5])
        assert cache.get(long_text) == [0.5]

    def test_unicode_text(self):
        cache = _EmbeddingCache(max_size=10)
        texts = ["héllo wörld", "日本語", "👋🌍", "¿Qué tal?"]
        for t in texts:
            cache.put(t, [1.0])
        for t in texts:
            assert cache.get(t) == [1.0]

    def test_empty_string(self):
        cache = _EmbeddingCache(max_size=10)
        cache.put("", [0.0])
        assert cache.get("") == [0.0]

    def test_special_chars(self):
        cache = _EmbeddingCache(max_size=10)
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        cache.put(text, [0.5])
        assert cache.get(text) == [0.5]

    def test_newlines_and_tabs(self):
        cache = _EmbeddingCache(max_size=10)
        text = "line1\nline2\t tabbed"
        cache.put(text, [0.5])
        assert cache.get(text) == [0.5]

    def test_identical_md5_different_text(self):
        cache = _EmbeddingCache(max_size=10)
        a = "text_a" * 100
        b = "text_b" * 100
        cache.put(a, [0.0])
        cache.put(b, [0.1])
        assert cache.get(a) == [0.0]
        assert cache.get(b) == [0.1]

    def test_cache_size_property(self):
        cache = _EmbeddingCache(max_size=5)
        assert cache.size == 0
        cache.put("a", [0.0])
        assert cache.size == 1
        cache.put("b", [0.1])
        assert cache.size == 2

    def test_cache_size_after_clear(self):
        cache = _EmbeddingCache(max_size=5)
        for i in range(5):
            cache.put(f"k{i}", [float(i)])
        assert cache.size == 5
        cache.clear()
        assert cache.size == 0


class TestEmbeddingCacheThreadSafety:
    def test_concurrent_puts(self):
        cache = _EmbeddingCache(max_size=100)
        errors = []

        def putter(key):
            try:
                for _ in range(100):
                    cache.put(key, [0.0])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=putter, args=(f"key{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"
        assert cache.size == 20

    def test_concurrent_gets_and_puts(self):
        cache = _EmbeddingCache(max_size=50)
        for i in range(30):
            cache.put(f"key{i}", [float(i)])

        errors = []

        def worker():
            try:
                for _ in range(100):
                    cache.put("new_key", [0.5])
                    cache.get("key1")
                    cache.size
                    cache.get_stats()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"

    def test_concurrent_clear(self):
        cache = _EmbeddingCache(max_size=50)
        errors = []

        def clearer():
            try:
                for _ in range(50):
                    cache.clear()
                    cache.put("a", [0.0])
                    cache.get("a")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=clearer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"

    def test_concurrent_eviction_no_crash(self):
        cache = _EmbeddingCache(max_size=10)
        errors = []

        def worker():
            try:
                for i in range(500):
                    cache.put(f"key{i % 30}", [float(i)])
                    cache.get(f"key{(i + 1) % 30}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred: {errors}"
        assert cache.size <= 10


class TestEmbeddingFunctionCache:
    @pytest.fixture
    def mock_embedding(self):
        emb = _SentenceTransformerEmbedding("test-model", cache_size=10)

        class MockModel:
            def encode(self, texts, **kwargs):
                import numpy as np
                return np.array([[hash(t) % 1000 / 1000.0 for _ in range(4)] for t in texts])

        emb._model = MockModel()
        return emb

    def test_cache_hits_on_repeated_call(self, mock_embedding):
        r1 = mock_embedding(["hello", "world"])
        r2 = mock_embedding(["hello", "world"])
        assert r1 == r2
        assert mock_embedding.get_cache_stats()["size"] == 2

    def test_partial_cache_hit(self, mock_embedding):
        r1 = mock_embedding(["hello", "world"])
        assert mock_embedding.get_cache_stats()["size"] == 2

        r2 = mock_embedding(["hello", "new"])
        assert mock_embedding.get_cache_stats()["size"] == 3
        assert r2[0] == r1[0]

    def test_no_cache_new_texts(self, mock_embedding):
        r1 = mock_embedding(["text1"])
        r2 = mock_embedding(["text2"])
        assert r1 != r2
        assert mock_embedding.get_cache_stats()["size"] == 2

    def test_cache_size_with_repeated_texts(self, mock_embedding):
        for _ in range(10):
            mock_embedding(["hello"])
        assert mock_embedding.get_cache_stats()["size"] == 1

    def test_clear_cache(self, mock_embedding):
        mock_embedding(["hello", "world"])
        assert mock_embedding.get_cache_stats()["size"] == 2
        mock_embedding.clear_cache()
        assert mock_embedding.get_cache_stats()["size"] == 0

    def test_cache_works_with_empty_input(self, mock_embedding):
        result = mock_embedding([])
        assert result == []

    def test_cache_works_with_single_character(self, mock_embedding):
        r1 = mock_embedding(["a"])
        r2 = mock_embedding(["a"])
        assert r1 == r2

    def test_cache_works_with_unicode(self, mock_embedding):
        texts = ["café", "résumé", "jalapeño", "naïve"]
        r1 = mock_embedding(texts)
        r2 = mock_embedding(texts)
        assert r1 == r2
