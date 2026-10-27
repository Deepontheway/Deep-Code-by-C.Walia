from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_approvals_state ON approvals(state, expires_at);
                """
            )

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
                FROM sessions s
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_session(self, title: str | None = None) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        now = time.time()
        clean_title = (title or "New chat").strip()[:120] or "New chat"
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, clean_title, now, now),
            )
        return {"id": session_id, "title": clean_title, "created_at": now, "updated_at": now}

    def has_session(self, session_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def messages(self, session_id: str, limit: int = 30) -> list[dict[str, Any]]:
        query = "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC"
        params: list[Any] = [session_id]
        if limit and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    def create_approval(self, session_id: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        approval_id = uuid.uuid4().hex
        now = time.time()
        expires = now + 900
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO approvals (id, session_id, kind, payload, state, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (approval_id, session_id, kind, json.dumps(payload, ensure_ascii=False), "pending", now, expires),
            )
        return {
            "id": approval_id,
            "session_id": session_id,
            "kind": kind,
            "payload": payload,
            "state": "pending",
            "created_at": now,
            "expires_at": expires,
        }

    def _expire_stale(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE approvals SET state = 'expired' WHERE state = 'pending' AND expires_at < ?",
            (time.time(),),
        )

    def pending_approvals(self, session_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            self._expire_stale(conn)
            if session_id:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE state = 'pending' AND session_id = ? ORDER BY created_at ASC",
                    (session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM approvals WHERE state = 'pending' ORDER BY created_at ASC"
                ).fetchall()
        return [self._approval(row) for row in rows]

    def resolve_approval(self, approval_id: str, approved: bool) -> dict[str, Any] | None:
        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None or row["state"] != "pending":
                return None
            if row["expires_at"] < now:
                conn.execute("UPDATE approvals SET state = 'expired' WHERE id = ?", (approval_id,))
                updated = dict(row)
                updated["state"] = "expired"
                updated["payload"] = json.loads(row["payload"])
                return updated
            state = "approved" if approved else "rejected"
            conn.execute("UPDATE approvals SET state = ? WHERE id = ?", (state, approval_id))
            updated = dict(row)
            updated["state"] = state
            updated["payload"] = json.loads(row["payload"])
            return updated

    @staticmethod
    def _approval(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["payload"] = json.loads(data["payload"])
        except (TypeError, ValueError):
            data["payload"] = {}
        return data
