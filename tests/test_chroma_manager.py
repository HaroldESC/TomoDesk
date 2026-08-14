import pytest

from src.memory.chroma_manager import ChromaManager

COLLECTIONS = ["personality", "memories", "context_rules", "episodic_memory"]


@pytest.fixture
def chroma(tmp_path):
    persist_path = tmp_path / "chroma_test"
    manager = ChromaManager(persist_path, "all-MiniLM-L6-v2")
    manager.initialize()
    yield manager


def test_initialize_creates_all_collections(chroma):
    for name in COLLECTIONS:
        count = chroma.count(name)
        assert count == 0, f"Collection {name} should be empty initially"


def test_add_and_query_document(chroma):
    chroma.add_to_collection(
        "memories",
        ["The user likes Python programming"],
        [{"type": "fact", "timestamp": "2026-01-01", "importance": 0.5}],
        ["doc1"],
    )
    results = chroma.query_collection("memories", "Python", n_results=1)
    assert len(results) == 1
    assert results[0]["id"] == "doc1"
    assert "Python" in results[0]["document"]


def test_add_to_all_collections(chroma):
    for name in COLLECTIONS:
        chroma.add_to_collection(
            name,
            [f"Test document for {name}"],
            [{"test": True}],
            [f"{name}_001"],
        )
    for name in COLLECTIONS:
        assert chroma.count(name) == 1


def test_delete_document(chroma):
    chroma.add_to_collection(
        "personality",
        ["Test trait"],
        [{"_dummy": "1"}],
        ["trait1"],
    )
    assert chroma.count("personality") == 1
    chroma.delete_from_collection("personality", ["trait1"])
    assert chroma.count("personality") == 0


def test_get_all(chroma):
    chroma.add_to_collection(
        "context_rules",
        ["Rule one", "Rule two"],
        [{"trigger": "app_open"}, {"trigger": "idle"}],
        ["rule1", "rule2"],
    )
    items = chroma.get_all("context_rules")
    assert len(items) == 2


def test_count(chroma):
    assert chroma.count("memories") == 0
    chroma.add_to_collection(
        "memories",
        ["Doc A", "Doc B", "Doc C"],
        [{"_dummy": "1"}, {"_dummy": "2"}, {"_dummy": "3"}],
        ["a", "b", "c"],
    )
    assert chroma.count("memories") == 3


class TestQueryCache:
    def test_cache_hit_and_miss(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        result = cache.get("memories", "Python", 5)
        assert result is None

        fake_result = [{"id": "doc1", "document": "Python", "metadata": {}, "distance": 0.1}]
        cache.put("memories", "Python", 5, fake_result)
        assert cache.get("memories", "Python", 5) == fake_result

    def test_cache_different_key_no_hit(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        cache.put("memories", "Python", 5, [{"id": "x"}])
        assert cache.get("memories", "Java", 5) is None
        assert cache.get("memories", "Python", 10) is None
        assert cache.get("context_rules", "Python", 5) is None

    def test_cache_ttl_expiry(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=0)
        cache.put("memories", "Python", 5, [{"id": "doc1"}])
        result = cache.get("memories", "Python", 5)
        assert result is None

    def test_cache_max_size_eviction(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=2, ttl=300)
        cache.put("a", "q1", 1, ["r1"])
        cache.put("b", "q2", 1, ["r2"])
        cache.put("c", "q3", 1, ["r3"])
        assert cache.get("a", "q1", 1) is None
        assert cache.size == 2

    def test_cache_invalidate_all(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        cache.put("a", "q1", 1, ["r1"])
        cache.put("b", "q2", 1, ["r2"])
        cache.invalidate_all()
        assert cache.size == 0
        assert cache.get("a", "q1", 1) is None

    def test_query_collection_caches_result(self, chroma):
        chroma.add_to_collection(
            "memories",
            ["The user likes Python"],
            [{"type": "fact"}],
            ["doc1"],
        )
        result1 = chroma.query_collection("memories", "Python", n_results=1)
        assert len(result1) == 1
        assert chroma._query_cache.size == 1
        # Second call hits cache — same result
        result2 = chroma.query_collection("memories", "Python", n_results=1)
        assert result1 == result2
        assert chroma._query_cache.size == 1

    def test_add_invalidates_cache(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        fake = [{"id": "old"}]
        cache.put("memories", "query", 5, fake)
        chroma._query_cache = cache
        assert chroma._query_cache.size == 1
        chroma.add_to_collection(
            "memories", ["new doc"], [{"type": "test"}], ["new_id"]
        )
        assert chroma._query_cache.size == 0

    def test_delete_invalidates_cache(self, chroma):
        chroma.add_to_collection(
            "personality", ["trait"], [{"_dummy": "1"}], ["t1"]
        )
        chroma._query_cache.invalidate_all()
        assert chroma._query_cache.size == 0

    def test_update_invalidates_cache(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        fake = [{"id": "stale"}]
        cache.put("memories", "x", 5, fake)
        chroma._query_cache = cache
        chroma.update_in_collection("memories", ids=["nonexistent"])
        assert chroma._query_cache.size == 0

    def test_cache_stats(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=50, ttl=600)
        cache.put("a", "q", 1, ["r"])
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 50
        assert stats["ttl_seconds"] == 600

    def test_cache_size_property(self, chroma):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=10, ttl=300)
        assert cache.size == 0
        cache.put("a", "q", 1, ["r"])
        assert cache.size == 1
