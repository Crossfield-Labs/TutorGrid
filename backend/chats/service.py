"""Chat 业务封装。"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from backend.chats.store import ChatMessageRow, ChatSessionRow, ChatStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_session_id() -> str:
    return f"chat_{uuid.uuid4().hex[:12]}"


def _new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


class ChatService:
    def __init__(self, db_path: Path) -> None:
        self.store = ChatStore(db_path)

    # -------- sessions --------

    def list_sessions(self, hyperdoc_id: str) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.store.list_sessions(hyperdoc_id)]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.store.get_session(session_id)
        return row.to_dict() if row else None

    def create_session(self, *, hyperdoc_id: str, title: str = "") -> dict[str, Any]:
        if not hyperdoc_id.strip():
            raise ValueError("hyperdoc_id 不能为空")
        now = _now_ms()
        row = ChatSessionRow(
            id=_new_session_id(),
            hyperdoc_id=hyperdoc_id.strip(),
            title=title.strip() or "默认会话",
            created_at=now,
            last_active_at=now,
        )
        self.store.upsert_session(row)
        return row.to_dict()

    def ensure_session(
        self,
        *,
        session_id: str,
        hyperdoc_id: str,
        title: str = "",
    ) -> dict[str, Any]:
        """SSE 端点用：传入 session_id 如果不存在就建一个，存在就更新 last_active_at。"""
        existing = self.store.get_session(session_id)
        now = _now_ms()
        if existing:
            self.store.update_session(session_id, last_active_at=now)
            return existing.to_dict()
        row = ChatSessionRow(
            id=session_id,
            hyperdoc_id=hyperdoc_id.strip() or "_global",
            title=title.strip() or "默认会话",
            created_at=now,
            last_active_at=now,
        )
        self.store.upsert_session(row)
        return row.to_dict()

    def rename_session(self, session_id: str, title: str) -> dict[str, Any] | None:
        row = self.store.update_session(session_id, title=title.strip())
        return row.to_dict() if row else None

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete_session(session_id)

    # -------- messages --------

    def list_messages(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.store.list_messages(session_id, limit)]

    def append_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if role not in ("user", "ai", "system"):
            raise ValueError(f"非法 role: {role}")
        row = ChatMessageRow(
            id=_new_message_id(),
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            timestamp=_now_ms(),
        )
        self.store.append_message(row)
        # 同步刷新 session 的 last_active_at
        self.store.update_session(session_id, last_active_at=row.timestamp)
        return row.to_dict()
