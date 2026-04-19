from __future__ import annotations

from pathlib import Path
from typing import Any

from sessions.state import OrchestratorSessionState
from storage.sqlite_store import SQLiteSessionStore


class SessionManager:
    def __init__(self, store: SQLiteSessionStore | None = None) -> None:
        self._sessions: dict[str, OrchestratorSessionState] = {}
        self._store = store or SQLiteSessionStore(
            Path(__file__).resolve().parents[1] / "scratch" / "storage" / "orchestrator.sqlite3"
        )

    def create(
        self,
        *,
        task_id: str,
        node_id: str,
        runner: str,
        workspace: str,
        task: str,
        goal: str,
    ) -> OrchestratorSessionState:
        session = OrchestratorSessionState(
            task_id=task_id,
            node_id=node_id,
            runner=runner,
            workspace=workspace,
            task=task,
            goal=goal or task,
        )
        self._sessions[session.session_id] = session
        self._store.save_session(session)
        self._store.save_snapshot(session)
        return session

    def get(self, session_id: str) -> OrchestratorSessionState | None:
        return self._sessions.get(session_id)

    def update(self, session: OrchestratorSessionState) -> None:
        self._sessions[session.session_id] = session
        session.touch()
        self._store.save_session(session)
        self._store.save_snapshot(session)

    def enqueue_followup(self, session_id: str, *, text: str, intent: str, target: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        item = {"followup": {"text": text, "intent": intent, "target": target}}
        session.followups.append(item["followup"])
        session.touch()
        self._store.save_session(session)
        self._store.save_snapshot(session)
        return item

    def list_sessions(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._store.list_sessions(limit=limit)

