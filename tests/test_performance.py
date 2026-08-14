import pytest


class TestEmbeddingCacheBenchmark:
    def test_cache_hit_vs_miss(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache

        cache = _EmbeddingCache(max_size=1000)
        for i in range(100):
            cache.put(f"text_{i}", [float(i)] * 384)

        def query_cache():
            for i in range(200):
                cache.get(f"text_{i % 100}")
                cache.get(f"never_cached_{i}")

        benchmark(query_cache)

    def test_eviction_overhead(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache

        cache = _EmbeddingCache(max_size=50)

        def evict_loop():
            for i in range(200):
                cache.put(f"text_{i}", [float(i)] * 384)

        benchmark(evict_loop)

    def test_thread_safety_overhead(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache
        import threading

        cache = _EmbeddingCache(max_size=1000)

        def worker():
            for i in range(50):
                cache.put(f"t_{i}", [1.0] * 384)
                cache.get(f"t_{i}")

        def run_concurrent():
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        benchmark(run_concurrent)


class TestBatchLoggingBenchmark:
    def test_batch_vs_individual(self, benchmark):
        from src.memory.database import DatabaseManager
        import tempfile
        import os
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseManager(db_path)
            db.initialize()

            rows = [
                ("system_event", json.dumps({"detail": "benchmark"}))
                for _ in range(100)
            ]

            def run_batch():
                db.execute_many(
                    "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
                    rows,
                )

            benchmark(run_batch)

            db.close()

    def test_individual_inserts(self, benchmark):
        from src.memory.database import DatabaseManager
        import tempfile
        import os
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseManager(db_path)
            db.initialize()

            def run_individual():
                for i in range(100):
                    db.execute(
                        "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
                        ("system_event", json.dumps({"detail": f"benchmark {i}"})),
                    )

            benchmark(run_individual)

            db.close()


class TestQueryCacheBenchmark:
    def test_cache_hit(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)
        for i in range(50):
            cache.put("col", f"query_{i}", 5, [{"id": f"doc_{i}"}])

        def query_hits():
            for i in range(50):
                cache.get("col", f"query_{i}", 5)

        benchmark(query_hits)

    def test_uncached_queries(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)
        for i in range(10):
            cache.put("col", f"q{i}", 5, [{"id": "x"}])

        def miss_queries():
            for i in range(100):
                cache.get("col", f"unknown_{i}", 5)

        benchmark(miss_queries)

    def test_put_and_invalidate(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)

        def write_and_invalidate():
            for i in range(20):
                cache.put("col", f"q{i}", 5, [{"id": str(i)}])
            cache.invalidate_all()

        benchmark(write_and_invalidate)


class TestHasRecentSuggestionBenchmark:
    def test_has_recent_suggestion(self, benchmark):
        from src.memory.database import DatabaseManager
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseManager(db_path)
            db.initialize()

            for i in range(500):
                db.execute(
                    "INSERT INTO episodic_log (source, summary, importance_score, timestamp) VALUES (?, ?, ?, datetime('now'))",
                    ("suggestion" if i < 10 else "user_message", f"summary {i}", 0.5),
                )
            db.commit()

            def query():
                rows = db.execute(
                    "SELECT 1 FROM episodic_log WHERE source='suggestion' AND timestamp > datetime('now', '-1 hours') LIMIT 1",
                )
                return bool(len(rows.fetchall()))

            benchmark(query)

            db.close()
