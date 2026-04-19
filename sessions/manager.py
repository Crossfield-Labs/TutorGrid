from __future__ import annotations

from sessions.state import OrchestratorSessionState


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, OrchestratorSessionState] = {}

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
        return session

    def get(self, session_id: str) -> OrchestratorSessionState | None:
        return self._sessions.get(session_id)

    def update(self, session: OrchestratorSessionState) -> None:
        self._sessions[session.session_id] = session
        session.touch()

    def enqueue_followup(self, session_id: str, *, text: str, intent: str, target: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        item = {"followup": {"text": text, "intent": intent, "target": target}}
        session.followups.append(item["followup"])
        session.touch()
        return item

