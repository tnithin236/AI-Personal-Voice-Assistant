"""Conversation + message persistence (SQLite)."""
from __future__ import annotations

import json
import time
import uuid

from .database import Database


class ConversationRepo:
    def __init__(self, db: Database):
        self.db = db

    def create(self, title: str = "New conversation") -> str:
        cid, now = uuid.uuid4().hex, time.time()
        self.db.run("INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                    (cid, title, now, now))
        return cid

    def exists(self, cid: str) -> bool:
        return bool(self.db.query("SELECT 1 FROM conversations WHERE id=?", (cid,)))

    def list(self, limit: int = 200) -> list[dict]:
        return self.db.query(
            "SELECT c.id, c.title, c.created_at, c.updated_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS message_count "
            "FROM conversations c ORDER BY c.updated_at DESC LIMIT ?", (limit,))

    def get(self, cid: str) -> dict | None:
        rows = self.db.query("SELECT id,title,created_at,updated_at FROM conversations WHERE id=?", (cid,))
        if not rows:
            return None
        conv = rows[0]
        conv["messages"] = self.messages(cid)
        return conv

    def messages(self, cid: str, limit: int | None = None) -> list[dict]:
        rows = self.db.query("SELECT id,role,content,language,meta,created_at FROM messages "
                             "WHERE conversation_id=? ORDER BY id", (cid,))
        for r in rows:
            r["meta"] = json.loads(r["meta"]) if r["meta"] else None
        return rows[-limit:] if limit else rows

    def add_message(self, cid: str, role: str, content: str, language: str | None = None,
                    meta: dict | None = None) -> int:
        now = time.time()
        mid = self.db.run("INSERT INTO messages(conversation_id,role,content,language,meta,created_at) "
                          "VALUES(?,?,?,?,?,?)",
                          (cid, role, content, language, json.dumps(meta) if meta else None, now))
        self.db.run("UPDATE conversations SET updated_at=? WHERE id=?", (now, cid))
        if role == "user":
            conv = self.db.query("SELECT title FROM conversations WHERE id=?", (cid,))[0]
            if conv["title"] == "New conversation":
                title = " ".join(content.split())[:48] or "New conversation"
                self.db.run("UPDATE conversations SET title=? WHERE id=?", (title, cid))
        return mid

    def delete_last_assistant(self, cid: str) -> None:
        rows = self.db.query("SELECT id, role FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1", (cid,))
        if rows and rows[0]["role"] == "assistant":
            self.db.run("DELETE FROM messages WHERE id=?", (rows[0]["id"],))

    def last_user_text(self, cid: str) -> str | None:
        rows = self.db.query("SELECT content FROM messages WHERE conversation_id=? AND role='user' "
                             "ORDER BY id DESC LIMIT 1", (cid,))
        return rows[0]["content"] if rows else None

    def rename(self, cid: str, title: str) -> None:
        self.db.run("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:80] or "Untitled", cid))

    def clear(self, cid: str) -> None:
        self.db.run("DELETE FROM messages WHERE conversation_id=?", (cid,))

    def delete(self, cid: str) -> None:
        self.db.run("DELETE FROM conversations WHERE id=?", (cid,))


class DocumentRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, doc_id: str, filename: str, path: str, chunks: int, pages: int | None, size: int) -> None:
        self.db.run("INSERT INTO documents(id,filename,path,chunks,pages,size_bytes,created_at) VALUES(?,?,?,?,?,?,?)",
                    (doc_id, filename, path, chunks, pages, size, time.time()))

    def list(self) -> list[dict]:
        return self.db.query("SELECT * FROM documents ORDER BY created_at DESC")

    def get(self, doc_id: str) -> dict | None:
        rows = self.db.query("SELECT * FROM documents WHERE id=?", (doc_id,))
        return rows[0] if rows else None

    def count(self) -> int:
        return self.db.query("SELECT COUNT(*) AS n FROM documents")[0]["n"]

    def delete(self, doc_id: str) -> None:
        self.db.run("DELETE FROM documents WHERE id=?", (doc_id,))
