"""Benchmarks that also assert the invariants of each operation.

The assertions are per-invocation invariants, never accumulated counters,
because ``benchmark`` runs the callable several times.
"""
import json
import os
import tempfile
import threading


class TestEmbeddingCacheBenchmark:
    def test_cache_hit_vs_miss(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache

        cache = _EmbeddingCache(max_size=1000)
        for i in range(100):
            cache.put(f"text_{i}", [float(i)] * 384)

        def query_cache():
            hits = 0
            misses = 0
            for i in range(200):
                if cache.get(f"text_{i % 100}") is not None:
                    hits += 1
                if cache.get(f"never_cached_{i}") is None:
                    misses += 1
            return hits, misses

        assert benchmark(query_cache) == (200, 200)
        # Leer no cambia el tamano ni ensucia el contenido.
        assert cache.get_stats()["size"] == 100
        assert cache.get("text_0") == [0.0] * 384
        assert cache.get("text_99") == [99.0] * 384
        assert cache.get("never_cached_0") is None

    def test_eviction_overhead(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache

        cache = _EmbeddingCache(max_size=50)

        def evict_loop():
            for i in range(200):
                cache.put(f"text_{i}", [float(i)] * 384)

        benchmark(evict_loop)

        # Ventana LRU exacta: solo sobreviven las 50 ultimas insertadas.
        assert cache.get_stats()["size"] == 50
        assert cache.get_stats()["max_size"] == 50
        alive = [i for i in range(200) if cache.get(f"text_{i}") is not None]
        assert alive == list(range(150, 200))
        assert cache.get("text_149") is None
        assert cache.get("text_199") == [199.0] * 384

    def test_thread_safety_overhead(self, benchmark):
        from src.memory.chroma_manager import _EmbeddingCache

        cache = _EmbeddingCache(max_size=1000)
        errors = []

        def worker():
            try:
                for i in range(50):
                    cache.put(f"t_{i}", [1.0] * 384)
                    cache.get(f"t_{i}")
            except Exception as exc:  # pragma: no cover - solo con carrera real
                errors.append(exc)

        def run_concurrent():
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        benchmark(run_concurrent)

        assert errors == []
        # 4 hilos escriben las mismas 50 claves: no se duplican ni se pierden.
        assert cache.size == 50
        assert all(cache.get(f"t_{i}") == [1.0] * 384 for i in range(50))


class TestBatchLoggingBenchmark:
    def test_batch_vs_individual(self, benchmark):
        from src.memory.database import DatabaseManager

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

            before = db.execute(
                "SELECT COUNT(*) AS c FROM interaction_log"
            ).fetchone()["c"]
            benchmark(run_batch)
            db.commit()
            after = db.execute(
                "SELECT COUNT(*) AS c FROM interaction_log"
            ).fetchone()["c"]

            # Cada round inserta un lote completo de 100 filas.
            delta = after - before
            assert delta >= 100 and delta % 100 == 0

            distinct = db.execute(
                "SELECT COUNT(DISTINCT data_json) AS c FROM interaction_log"
            ).fetchone()["c"]
            assert distinct == 1  # todas las filas del lote son identicas
            assert db.execute(
                "SELECT COUNT(*) AS c FROM interaction_log WHERE event_type='system_event'"
            ).fetchone()["c"] == delta

            # Cerrar antes de que el temporal se borre: en Windows el WAL
            # de SQLite mantiene el fichero abierto.
            db.close()

        db.close()

    def test_individual_inserts(self, benchmark):
        from src.memory.database import DatabaseManager

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
            db.commit()

            payloads = {
                r["data_json"]
                for r in db.execute("SELECT data_json FROM interaction_log")
            }
            # Exactamente 100 cargas distintas: una por fila, a diferencia
            # del lote, que produce una sola carga repetida.
            assert payloads == {json.dumps({"detail": f"benchmark {i}"}) for i in range(100)}
            total = db.execute(
                "SELECT COUNT(*) AS c FROM interaction_log"
            ).fetchone()["c"]
            assert total >= 100 and total % 100 == 0

            db.close()


class TestQueryCacheBenchmark:
    def test_cache_hit(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)
        for i in range(50):
            cache.put("col", f"query_{i}", 5, [{"id": f"doc_{i}"}])

        def query_hits():
            return [cache.get("col", f"query_{i}", 5) for i in range(50)]

        assert benchmark(query_hits) == [[{"id": f"doc_{i}"}] for i in range(50)]
        assert cache.get_stats()["size"] == 50
        assert cache.get_stats()["max_size"] == 100
        assert cache.get_stats()["ttl_seconds"] == 300
        # La clave incluye n_results: otro limite es otro miss.
        assert cache.get("col", "query_0", 6) is None
        assert cache.get("other_col", "query_0", 5) is None

    def test_uncached_queries(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)
        for i in range(10):
            cache.put("col", f"q{i}", 5, [{"id": "x"}])

        def miss_queries():
            return [cache.get("col", f"unknown_{i}", 5) for i in range(100)]

        assert benchmark(miss_queries) == [None] * 100
        # Un miss nunca inserta: el tamano se queda en las 10 previas.
        assert cache.size == 10
        assert cache.get_stats()["size"] == 10

    def test_put_and_invalidate(self, benchmark):
        from src.memory.chroma_manager import _QueryCache

        cache = _QueryCache(max_size=100, ttl=300)

        def write_and_invalidate():
            for i in range(20):
                cache.put("col", f"q{i}", 5, [{"id": str(i)}])
            assert cache.size == 20
            cache.invalidate_all()
            assert cache.size == 0

        benchmark(write_and_invalidate)

        assert cache.size == 0
        assert cache.get("col", "q0", 5) is None
        assert cache.get("col", "q19", 5) is None


class TestHasRecentSuggestionBenchmark:
    def test_has_recent_suggestion(self, benchmark):
        from src.memory.database import DatabaseManager

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

            assert benchmark(query) is True
            assert db.execute(
                "SELECT COUNT(*) AS c FROM episodic_log WHERE source='suggestion'"
            ).fetchone()["c"] == 10

            # Control negativo determinista: al alejar los timestamps, la
            # consulta debe dejar de encontrar nada. Sin esto, query podria
            # devolver True siempre y el test pasaria igual.
            db.execute(
                "UPDATE episodic_log SET timestamp = datetime('now','-5 hours') "
                "WHERE source='suggestion'"
            )
            db.commit()
            assert query() is False

            db.close()
