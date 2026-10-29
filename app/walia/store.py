from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MEMORY_STOPWORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for", "from",
    "has", "have", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "please", "so",
    "that", "the", "this", "to", "we", "with", "you", "your",
}
SECRET_MEMORY_PATTERN = re.compile(
    r"(?i)\b(api[ _-]?key|password|passwd|secret|token|bearer)\b\s*[:=]\s*\S+"
)
CAPTURE_PATTERNS = (
    re.compile(r"(?i)^\s*remember(?:\s+that)?\s*[:,]?\s*(.+)$"),
    re.compile(r"(?i)^\s*(?:please\s+)?(?:note|keep in mind)(?:\s+that)?\s*[:,]?\s*(.+)$"),
    re.compile(r"(?i)^\s*(i\s+(?:prefer|always|never|use|work\s+on|am\s+working\s+on)\b.+)$"),
    re.compile(r"(?i)^\s*(my\s+(?:name|project|stack|editor|os|timezone)\b.+)$"),
)


def _memory_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_+.-]{1,}", (text or "").lower())
        if token not in MEMORY_STOPWORDS and len(token) > 1
    }


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
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_usage_created ON usage(created_at);
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    importance INTEGER NOT NULL DEFAULT 3,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    last_used REAL NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at);
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

    def rename_session(self, session_id: str, title: str) -> dict[str, Any] | None:
        clean = (title or "").strip()[:120]
        if not clean:
            raise ValueError("Chat title cannot be empty.")
        now = time.time()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (clean, now, session_id),
            )
            if cursor.rowcount == 0:
                return None
        return {"id": session_id, "title": clean, "updated_at": now}

    def delete_session(self, session_id: str) -> bool:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM approvals WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

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

    def add_memory(
        self,
        content: str,
        tags: str = "",
        source: str = "manual",
        importance: int = 3,
    ) -> dict[str, Any]:
        clean = " ".join((content or "").split())[:1200]
        if not clean:
            raise ValueError("Memory text cannot be empty.")
        if SECRET_MEMORY_PATTERN.search(clean):
            raise ValueError("Memory looks like it contains a credential. Remove the secret and try again.")
        clean_tags = ",".join(
            item.strip()[:40] for item in (tags or "").split(",") if item.strip()
        )[:240]
        now = time.time()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM memories WHERE lower(content) = lower(?) LIMIT 1",
                (clean,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE memories SET tags = ?, source = ?, importance = ?, updated_at = ? WHERE id = ?",
                    (clean_tags, source[:40] or "manual", max(0, min(5, int(importance))), now, existing["id"]),
                )
                memory_id = existing["id"]
            else:
                memory_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO memories (id, content, tags, source, importance, created_at, updated_at, last_used) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                    (memory_id, clean, clean_tags, source[:40] or "manual", max(0, min(5, int(importance))), now, now),
                )
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return dict(row)

    def list_memories(self, limit: int = 100, query: str = "") -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            if (query or "").strip():
                return self._search_memories(conn, query, limit)
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
                (max(1, min(500, int(limit))),),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def _search_memories(
        self,
        conn: sqlite3.Connection,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        now = time.time()
        rows = conn.execute("SELECT * FROM memories ORDER BY updated_at DESC LIMIT 1000").fetchall()
        query_tokens = _memory_tokens(query)
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            content_tokens = _memory_tokens(row["content"] + " " + (row["tags"] or "").replace(",", " "))
            overlap = len(query_tokens & content_tokens)
            if query_tokens and overlap == 0:
                continue
            coverage = overlap / max(1, len(query_tokens))
            age_days = max(0.0, (now - float(row["updated_at"])) / 86400.0)
            recency = 1.0 / (1.0 + age_days / 45.0)
            score = coverage * 4.0 + overlap * 0.6 + float(row["importance"]) * 0.35 + recency
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        chosen = [row for _, row in scored[: max(1, min(100, int(limit)))]]
        if chosen:
            conn.executemany(
                "UPDATE memories SET last_used = ? WHERE id = ?",
                [(now, row["id"]) for row in chosen],
            )
        return [dict(row) for row in chosen]

    def memory_context(self, query: str, limit: int = 5) -> str:
        if not (query or "").strip():
            return ""
        with self._lock, self._connect() as conn:
            rows = self._search_memories(conn, query, limit)
        if not rows:
            return ""
        lines = []
        for row in rows:
            tags = f" [{row['tags']}]" if row.get("tags") else ""
            lines.append(f"- {row['content']}{tags}")
        return "\n".join(lines)

    def capture_memory(self, user_text: str) -> dict[str, Any] | None:
        text = " ".join((user_text or "").split())
        if not 8 <= len(text) <= 1200 or SECRET_MEMORY_PATTERN.search(text):
            return None
        for pattern in CAPTURE_PATTERNS:
            match = pattern.match(text)
            if not match:
                continue
            content = match.group(1).strip()
            if len(content) < 8:
                return None
            importance = 4 if text.lower().startswith(("remember", "note", "keep in mind")) else 3
            try:
                return self.add_memory(content, tags="auto", source="chat", importance=importance)
            except ValueError:
                return None
        return None

    def add_usage(
        self,
        session_id: str | None,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        if total_tokens <= 0 and prompt_tokens <= 0 and completion_tokens <= 0:
            return
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO usage (session_id, model, provider, prompt_tokens, completion_tokens, total_tokens, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, model, provider, int(prompt_tokens), int(completion_tokens), int(total_tokens), now),
            )

    def usage_summary(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            today = conn.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COUNT(*) AS requests
                FROM usage
                WHERE date(created_at, 'unixepoch', 'localtime') = date('now', 'localtime')
                """
            ).fetchone()
            total = conn.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                       COALESCE(SUM(total_tokens), 0) AS total_tokens,
                       COUNT(*) AS requests
                FROM usage
                """
            ).fetchone()
            by_model = conn.execute(
                """
                SELECT model, provider, SUM(total_tokens) AS total_tokens, COUNT(*) AS requests
                FROM usage
                GROUP BY model, provider
                ORDER BY total_tokens DESC
                LIMIT 10
                """
            ).fetchall()
        return {
            "today": dict(today),
            "total": dict(total),
            "by_model": [dict(row) for row in by_model],
        }

    @staticmethod
    def _approval(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["payload"] = json.loads(data["payload"])
        except (TypeError, ValueError):
            data["payload"] = {}
        return data
