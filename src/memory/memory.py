import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from src.memory.chroma_manager import ChromaManager
from src.memory.database import DatabaseManager

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(
        self,
        db_manager: DatabaseManager,
        chroma_manager: ChromaManager,
        config: dict,
    ):
        self._db = db_manager
        self._chroma = chroma_manager
        self._config = config
        self._max_short_term = config["memory"].get("max_short_term_messages", 20)
        self.short_term_messages: List[Dict[str, str]] = []

    # ── Short-term memory ──────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        self.short_term_messages.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )
        if len(self.short_term_messages) > self._max_short_term:
            self.short_term_messages.pop(0)

    def get_recent_messages(self, n: int | None = None) -> List[Dict[str, str]]:
        if n is None:
            return list(self.short_term_messages)
        return self.short_term_messages[-n:]

    def clear_short_term(self) -> None:
        self.short_term_messages.clear()

    # ── Notes (SQLite) ─────────────────────────────────────────────────

    def add_note(self, title: str, content: str, tags: str = "") -> int:
        cursor = self._db.execute(
            "INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)",
            (title, content, tags),
        )
        self._db.commit()
        note_id = cursor.lastrowid
        self._index_note(note_id, title, content)
        return note_id

    def _index_note(self, note_id: int, title: str, content: str) -> None:
        document = f"{title}\n{content}"
        self._chroma.add_to_collection(
            "notes_index",
            documents=[document],
            metadatas=[{"note_id": note_id, "title": title}],
            ids=[f"note_{note_id}"],
        )

    def _deindex_note(self, note_id: int) -> None:
        try:
            self._chroma.delete_from_collection("notes_index", [f"note_{note_id}"])
        except Exception:
            logger.warning(f"Failed to deindex note {note_id}", exc_info=True)

    def search_notes_semantic(self, query: str, n: int = 5) -> List[Dict]:
        return self._chroma.query_collection("notes_index", query, n_results=n)

    def get_note(self, note_id: int) -> Dict | None:
        cursor = self._db.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_notes(self) -> List[Dict]:
        cursor = self._db.execute(
            "SELECT * FROM notes ORDER BY id DESC LIMIT 500"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_note(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
        tags: str | None = None,
    ) -> None:
        fields = []
        params = []
        if title is not None:
            fields.append("title = ?")
            params.append(title)
        if content is not None:
            fields.append("content = ?")
            params.append(content)
        if tags is not None:
            fields.append("tags = ?")
            params.append(tags)
        if not fields:
            return
        fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(note_id)
        self._db.execute(
            f"UPDATE notes SET {', '.join(fields)} WHERE id = ?", params
        )
        self._db.commit()

    def delete_note(self, note_id: int) -> None:
        self._deindex_note(note_id)
        self._db.execute(
            "DELETE FROM notes WHERE id = ?", (note_id,)
        )
        self._db.commit()

    # ── Reminders (SQLite) ─────────────────────────────────────────────

    def add_reminder(
        self, message: str, trigger_time: str, recurring: str | None = None
    ) -> int:
        cursor = self._db.execute(
            "INSERT INTO reminders (message, trigger_time, recurring) VALUES (?, ?, ?)",
            (message, trigger_time, recurring),
        )
        self._db.commit()
        return cursor.lastrowid

    def get_due_reminders(self) -> List[Dict]:
        cursor = self._db.execute(
            "SELECT * FROM reminders WHERE trigger_time <= datetime('now') AND active = 1"
        )
        return [dict(row) for row in cursor.fetchall()]

    def deactivate_reminder(self, reminder_id: int) -> None:
        self._db.execute(
            "UPDATE reminders SET active = 0 WHERE id = ?", (reminder_id,)
        )
        self._db.commit()

    def list_reminders(self, active_only: bool = True) -> List[Dict]:
        if active_only:
            cursor = self._db.execute(
                "SELECT * FROM reminders WHERE active = 1 ORDER BY trigger_time ASC"
            )
        else:
            cursor = self._db.execute(
                "SELECT * FROM reminders ORDER BY trigger_time ASC"
            )
        return [dict(row) for row in cursor.fetchall()]

    # ── Interaction log (SQLite) ───────────────────────────────────────

    def log_interaction(self, event_type: str, data: Dict | None = None) -> None:
        data_json = json.dumps(data) if data else None
        self._db.execute(
            "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
            (event_type, data_json),
        )
        self._db.commit()

    def log_interactions_batch(self, events: list[tuple[str, Dict | None]]) -> None:
        if not events:
            return
        params = [
            (event_type, json.dumps(data) if data else None)
            for event_type, data in events
        ]
        self._db.execute_many(
            "INSERT INTO interaction_log (event_type, data_json) VALUES (?, ?)",
            params,
        )
        self._db.commit()

    # ── Episodic log (SQLite) ──────────────────────────────────────────

    def add_episodic_log(
        self, summary: str, importance_score: float, source: str, chroma_id: str | None = None
    ) -> int:
        cursor = self._db.execute(
            "INSERT INTO episodic_log (summary, importance_score, source, chroma_id) VALUES (?, ?, ?, ?)",
            (summary, importance_score, source, chroma_id),
        )
        self._db.commit()
        return cursor.lastrowid

    # ── User profile (SQLite) ──────────────────────────────────────────

    def get_preference(self, key: str) -> str | None:
        cursor = self._db.execute(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_preference(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO user_profile (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = CURRENT_TIMESTAMP",
            (key, value),
        )
        self._db.commit()

    # ── Long-term memory (ChromaDB) ────────────────────────────────────

    def add_long_term_memory(
        self,
        content: str,
        memory_type: str,
        importance: float = 0.5,
        metadata: Dict | None = None,
    ) -> str:
        doc_id = uuid.uuid4().hex
        meta = {"type": memory_type, "timestamp": datetime.now().isoformat(), "importance": importance}
        if metadata:
            meta.update(metadata)
        self._chroma.add_to_collection(
            "memories", [content], [meta], [doc_id]
        )
        return doc_id

    def query_memories(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        return self._chroma.query_collection("memories", query, n_results=n)

    # ── Personality (ChromaDB) ─────────────────────────────────────────

    def add_personality_trait(self, description: str) -> str:
        doc_id = uuid.uuid4().hex
        self._chroma.add_to_collection(
            "personality", [description], [{"trait": description[:50]}], [doc_id]
        )
        return doc_id

    def query_personality(self, query: str, n: int = 3) -> List[Dict[str, Any]]:
        return self._chroma.query_collection("personality", query, n_results=n)

    # ── Context rules (ChromaDB) ───────────────────────────────────────

    def add_context_rule(
        self, trigger_desc: str, app: str | None = None, document: str = ""
    ) -> str:
        doc_id = uuid.uuid4().hex
        meta = {"trigger": trigger_desc, "app": app, "active": True}
        self._chroma.add_to_collection(
            "context_rules", [document or trigger_desc], [meta], [doc_id]
        )
        return doc_id

    def get_context_rules(self) -> List[Dict[str, Any]]:
        all_rules = self._chroma.get_all("context_rules")
        return [r for r in all_rules if r.get("metadata", {}).get("active", True)]

    # ── Episodic memory (ChromaDB + SQLite) ────────────────────────────

    def add_episodic_memory(
        self, summary: str, importance_score: float, source: str = "manual"
    ) -> str:
        doc_id = f"episodic_{uuid.uuid4().hex[:12]}"
        meta = {
            "timestamp": datetime.now().isoformat(),
            "importance_score": importance_score,
            "source": source,
        }
        self._chroma.add_to_collection(
            "episodic_memory", [summary], [meta], [doc_id]
        )
        self.add_episodic_log(summary, importance_score, source, chroma_id=doc_id)
        return doc_id

    def query_episodic(self, query: str, n: int = 3) -> List[Dict[str, Any]]:
        return self._chroma.query_collection("episodic_memory", query, n_results=n)

    def list_episodic_log(self) -> List[Dict]:
        cursor = self._db.execute(
            "SELECT id, timestamp, summary, importance_score, source, chroma_id FROM episodic_log ORDER BY timestamp DESC LIMIT 500"
        )
        return [dict(row) for row in cursor.fetchall()]

    def has_recent_suggestion(self, hours: int = 1) -> bool:
        cursor = self._db.execute(
            "SELECT 1 FROM episodic_log WHERE source = 'suggestion' "
            "AND timestamp > datetime('now', ?) LIMIT 1",
            (f"-{hours} hours",),
        )
        return cursor.fetchone() is not None

    def delete_episodic_memory(self, log_id: int) -> bool:
        cursor = self._db.execute(
            "SELECT summary, chroma_id FROM episodic_log WHERE id = ?", (log_id,)
        )
        row = cursor.fetchone()
        if not row:
            return False

        chroma_id = row["chroma_id"]
        self._db.execute("DELETE FROM episodic_log WHERE id = ?", (log_id,))
        self._db.commit()

        if chroma_id:
            try:
                self._chroma.delete_from_collection("episodic_memory", [chroma_id])
            except Exception:
                logger.warning("Could not delete from ChromaDB")
        else:
            logger.warning("Episodic memory %d has no chroma_id, skipping ChromaDB deletion", log_id)

        return True
