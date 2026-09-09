"""SQLite persistence for chat threads, messages, and per-node token usage logs."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

from Utility.config.settings import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_threads (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pending_query TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS token_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
    node TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_tokens_thread ON token_usage_log(thread_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ChatThread:
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    pending_query: Optional[str]
    status: Optional[str]


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    citations: list[str]
    confidence: Optional[float]
    created_at: str


class ChatStore:
    """SQLite-backed store for chat threads, messages, and per-node token usage."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = Path(db_path or settings.sqlite_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def create_thread(self, title: str) -> str:
        thread_id = uuid4().hex
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_threads (thread_id, title, created_at, updated_at, pending_query, status) "
                "VALUES (?, ?, ?, ?, NULL, NULL)",
                (thread_id, title, now, now),
            )
        return thread_id

    def list_threads(self) -> list[ChatThread]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM chat_threads ORDER BY updated_at DESC").fetchall()
        return [self._row_to_thread(r) for r in rows]

    def load_thread(self, thread_id: str) -> tuple[ChatThread | None, list[ChatMessage]]:
        with self._connect() as conn:
            thread_row = conn.execute(
                "SELECT * FROM chat_threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
            if thread_row is None:
                return None, []
            message_rows = conn.execute(
                "SELECT role, content, citations, confidence, created_at FROM chat_messages "
                "WHERE thread_id = ? ORDER BY id ASC",
                (thread_id,),
            ).fetchall()

        messages = [
            ChatMessage(
                role=r["role"],
                content=r["content"],
                citations=json.loads(r["citations"]) if r["citations"] else [],
                confidence=r["confidence"],
                created_at=r["created_at"],
            )
            for r in message_rows
        ]
        return self._row_to_thread(thread_row), messages

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        citations: list[str] | None = None,
        confidence: float | None = None,
    ) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages (thread_id, role, content, citations, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (thread_id, role, content, json.dumps(citations or []), confidence, now),
            )
            conn.execute("UPDATE chat_threads SET updated_at = ? WHERE thread_id = ?", (now, thread_id))

    def update_thread_state(self, thread_id: str, pending_query: str | None, status: str | None) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_threads SET pending_query = ?, status = ?, updated_at = ? WHERE thread_id = ?",
                (pending_query, status, now, thread_id),
            )

    def log_token_usage(
        self,
        thread_id: str,
        node: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        total_tokens: int | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO token_usage_log "
                "(thread_id, node, prompt_tokens, completion_tokens, total_tokens, latency_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    node,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens if total_tokens is not None else prompt_tokens + completion_tokens,
                    latency_ms,
                    _now(),
                ),
            )

    def get_today_tokens(self, thread_id: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) AS total FROM token_usage_log "
                "WHERE thread_id = ? AND substr(created_at, 1, 10) = ?",
                (thread_id, today),
            ).fetchone()
        return int(row["total"])

    def get_lifetime_tokens(self, thread_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) AS total FROM token_usage_log "
                "WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        return int(row["total"])

    def delete_threads_older_than(self, days: int, exclude_thread_id: str | None = None) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            if exclude_thread_id:
                cursor = conn.execute(
                    "DELETE FROM chat_threads WHERE updated_at < ? AND thread_id != ?",
                    (cutoff, exclude_thread_id),
                )
            else:
                cursor = conn.execute("DELETE FROM chat_threads WHERE updated_at < ?", (cutoff,))
            deleted = cursor.rowcount
        return deleted

    @staticmethod
    def _row_to_thread(row: sqlite3.Row) -> ChatThread:
        return ChatThread(
            thread_id=row["thread_id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            pending_query=row["pending_query"],
            status=row["status"],
        )
