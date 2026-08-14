import logging


_log = logging.getLogger(__name__)


class _ChromaError(RuntimeError):
    pass


class MockChroma:
    def __init__(self, fail_add=False, fail_query=False, fail_delete=False, fail_get=False):
        self.collections = {}
        self.fail_add = fail_add
        self.fail_query = fail_query
        self.fail_delete = fail_delete
        self.fail_get = fail_get

    def initialize(self):
        if self.fail_add:
            _log.exception("Simulated init failure")

    def add_to_collection(self, collection_name, documents, metadatas, ids):
        try:
            if self.fail_add:
                raise _ChromaError("Simulated add failure")
            for i, doc in enumerate(documents):
                self.collections.setdefault(collection_name, []).append({
                    "id": ids[i] if ids else None,
                    "document": doc,
                    "metadata": metadatas[i] if metadatas else {},
                })
        except Exception:
            _log.exception("MockChroma add_to_collection failed")

    def delete_from_collection(self, collection, doc_ids):
        try:
            if self.fail_delete:
                raise _ChromaError("Simulated delete failure")
            docs = self.collections.get(collection, [])
            self.collections[collection] = [d for d in docs if d["id"] not in doc_ids]
        except Exception:
            _log.exception("MockChroma delete_from_collection failed")

    def query_collection(self, collection, query, n_results=3):
        try:
            if self.fail_query:
                raise _ChromaError("Simulated query failure")
            docs = self.collections.get(collection, [])
            query_words = query.lower().split()
            scored = []
            for doc in docs:
                text = doc["document"].lower()
                word_matches = sum(1 for w in query_words if w in text)
                title = (doc.get("metadata", {}) or {}).get("title", "")
                title_matches = sum(1 for w in query_words if w in title.lower())
                score = word_matches * 2 + title_matches * 3
                scored.append((-score, doc))
            scored.sort(key=lambda x: (x[0], x[1]["id"]))
            return [s[1] for s in scored[:n_results]]
        except Exception:
            _log.exception("MockChroma query_collection failed")
            return []

    def get_all(self, collection):
        try:
            if self.fail_get:
                raise _ChromaError("Simulated get_all failure")
            return self.collections.get(collection, [])
        except Exception:
            _log.exception("MockChroma get_all failed")
            return []
