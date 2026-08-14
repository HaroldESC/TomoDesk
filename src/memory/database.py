import logging
import sqlite3
import threading
from pathlib import Path

from src.config.secure_files import secure_file

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT,
        tags TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        trigger_time TIMESTAMP NOT NULL,
        recurring TEXT DEFAULT NULL,
        active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS interaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        data_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS episodic_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        summary TEXT NOT NULL,
        importance_score REAL DEFAULT 0.5,
        source TEXT DEFAULT 'manual',
        chroma_id TEXT
    )
    """,
]

_DEFAULT_PROFILE_KEYS = [
    ("name", "User"),
    ("language", "es"),
]


class DatabaseManager:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        with self._lock:
            try:
                secure_file(self._db_path)
            except Exception:
                logger.warning(
                    "Failed to secure database file %s", self._db_path, exc_info=True
                )
            self._conn.executescript("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            for ddl in _CREATE_TABLES_SQL:
                self._conn.execute(ddl)

            self._migrate()

            for key, value in _DEFAULT_PROFILE_KEYS:
                self._conn.execute(
                    "INSERT OR IGNORE INTO user_profile (key, value) VALUES (?, ?)",
                    (key, value),
                )

            self._conn.commit()

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        if not params_list:
            return
        with self._lock:
            self._conn.executemany(sql, params_list)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def _migrate(self) -> None:
        try:
            self._conn.execute("ALTER TABLE episodic_log ADD COLUMN chroma_id TEXT")
        except sqlite3.OperationalError:
            pass

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        with self._lock:
            self._conn.close()
