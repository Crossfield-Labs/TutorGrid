"""SQLite 持久化层 - chat_sessions + chat_messages。

复用 scratch/storage/orchestrator.sqlite3。
跟 workspace_meta 同款写法（plain sqlite3，不引 SQLAlchemy）。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ChatSessionRow:
    id: str
    hyperdoc_id: str
    title: str
    created_at: int
    last_active_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hyperdocId": self.hyperdoc_id,
            "title": self.title,
            "createdAt": self.created_at,
            "lastActiveAt": self.last_active_at,
        }


@dataclass
class ChatMessageRow:
    id: str
    session_id: str
    role: str  # user | ai | system
    content: str
    metadata: dict[str, Any]
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class ChatStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id              TEXT PRIMARY KEY,
                    hyperdoc_id     TEXT NOT NULL,
                    title           TEXT NOT NULL DEFAULT '默认会话',
                    created_at      INTEGER NOT NULL,
                    last_active_at  INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_sessions_hyperdoc
                ON chat_sessions(hyperdoc_id, last_active_at DESC);

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id          TEXT PRIMARY KEY,
                    session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    timestamp   INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_chat_messages_session
                ON chat_messages(session_id, timestamp ASC);
                """
            )
            connection.commit()

    # -------------- chat_sessions --------------

    def list_sessions(self, hyperdoc_id: str) -> list[ChatSessionRow]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, hyperdoc_id, title, created_at, last_active_at "
                "FROM chat_sessions WHERE hyperdoc_id = ? "
                "ORDER BY last_active_at DESC",
                (hyperdoc_id,),
            ).fetchall()
            return [self._row_to_session(row) for row in rows]

    def get_session(self, session_id: str) -> ChatSessionRow | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id, hyperdoc_id, title, created_at, last_active_at "
                "FROM chat_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return self._row_to_session(row) if row else None

    def upsert_session(self, row: ChatSessionRow) -> None:
        """前端可能用自己生成的 sessionId 直接发消息（兜底兼容）。
        如果 session 不存在就建一个，存在就更新 last_active_at。"""
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO chat_sessions (id, hyperdoc_id, title, created_at, last_active_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_active_at = excluded.last_active_at
                """,
                (row.id, row.hyperdoc_id, row.title, row.created_at, row.last_active_at),
            )
            connection.commit()

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        last_active_at: int | None = None,
    ) -> ChatSessionRow | None:
        existing = self.get_session(session_id)
        if existing is None:
            return None
        new_title = title if title is not None else existing.title
        new_active = last_active_at if last_active_at is not None else existing.last_active_at
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE chat_sessions SET title = ?, last_active_at = ? WHERE id = ?",
                (new_title, new_active, session_id),
            )
            connection.commit()
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
            connection.commit()
            return cursor.rowcount > 0

    # -------------- chat_messages --------------

    def list_messages(self, session_id: str, limit: int = 200) -> list[ChatMessageRow]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, session_id, role, content, metadata, timestamp "
                "FROM chat_messages WHERE session_id = ? "
                "ORDER BY timestamp ASC LIMIT ?",
                (session_id, max(1, limit)),
            ).fetchall()
            return [self._row_to_message(row) for row in rows]

    def append_message(self, row: ChatMessageRow) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO chat_messages (id, session_id, role, content, metadata, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row.id,
                    row.session_id,
                    row.role,
                    row.content,
                    json.dumps(row.metadata, ensure_ascii=False),
                    row.timestamp,
                ),
            )
            connection.commit()

    # -------------- helpers --------------

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> ChatSessionRow:
        return ChatSessionRow(
            id=row["id"],
            hyperdoc_id=row["hyperdoc_id"],
            title=row["title"],
            created_at=row["created_at"],
            last_active_at=row["last_active_at"],
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> ChatMessageRow:
        meta_raw = row["metadata"] or "{}"
        try:
            metadata = json.loads(meta_raw)
        except json.JSONDecodeError:
            metadata = {}
        return ChatMessageRow(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            metadata=metadata,
            timestamp=row["timestamp"],
        )
