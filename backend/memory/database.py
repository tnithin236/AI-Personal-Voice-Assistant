"""SQLite wrapper + runtime settings store. No project imports, so it is easy to test."""
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL, content TEXT NOT NULL, language TEXT, meta TEXT, created_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, filename TEXT NOT NULL, path TEXT NOT NULL, chunks INTEGER NOT NULL,
  pages INTEGER, size_bytes INTEGER, created_at REAL NOT NULL);
"""


class Database:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def run(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class SettingsStore:
    """Runtime settings persisted as JSON values; unknown keys are rejected."""

    def __init__(self, db: Database, defaults: dict):
        self._db, self._defaults = db, dict(defaults)

    def all(self) -> dict:
        data = dict(self._defaults)
        for row in self._db.query("SELECT key, value FROM settings"):
            if row["key"] in data:
                try:
                    data[row["key"]] = json.loads(row["value"])
                except json.JSONDecodeError:
                    pass
        return data

    def get(self, key: str):
        return self.all()[key]

    def update(self, changes: dict) -> dict:
        unknown = set(changes) - set(self._defaults)
        if unknown:
            raise KeyError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
        for k, v in changes.items():
            self._db.run("INSERT INTO settings(key,value) VALUES(?,?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
        return self.all()

    def reset(self) -> dict:
        self._db.run("DELETE FROM settings")
        return self.all()
