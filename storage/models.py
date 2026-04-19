from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass

from sessions.state import OrchestratorSessionState


@dataclass(slots=True)
class SessionRow:
    session_id: str
    task_id: str
    node_id: str
    runner: str
    workspace: str
    task: str
    goal: str
    status: str
    phase: str
    stop_reason: str
    latest_summary: str
    latest_artifact_summary: str
    permission_summary: str
    session_info_summary: str
    mcp_status_summary: str
    active_worker: str
    active_session_mode: str
    active_worker_profile: str
    active_worker_task_id: str
    active_worker_can_interrupt: bool
    awaiting_input: bool
    pending_user_prompt: str
    snapshot_version: int
    created_at: str
    updated_at: str
    completed_at: str
    error: str

    @classmethod
    def from_session(cls, session: OrchestratorSessionState) -> "SessionRow":
        completed_at = session.updated_at if session.status in {"COMPLETED", "FAILED", "CANCELLED"} else ""
        return cls(
            session_id=session.session_id,
            task_id=session.task_id,
            node_id=session.node_id,
            runner=session.runner,
            workspace=session.workspace,
            task=session.task,
            goal=session.goal,
            status=session.status,
            phase=session.phase,
            stop_reason=session.stop_reason,
            latest_summary=session.latest_summary,
            latest_artifact_summary=session.latest_artifact_summary,
            permission_summary=session.permission_summary,
            session_info_summary=session.session_info_summary,
            mcp_status_summary=session.mcp_status_summary,
            active_worker=session.active_worker,
            active_session_mode=session.active_session_mode,
            active_worker_profile=session.active_worker_profile,
            active_worker_task_id=session.active_worker_task_id,
            active_worker_can_interrupt=session.active_worker_can_interrupt,
            awaiting_input=session.awaiting_input,
            pending_user_prompt=session.pending_user_prompt,
            snapshot_version=session.snapshot_version,
            created_at=session.created_at,
            updated_at=session.updated_at,
            completed_at=completed_at,
            error=session.error,
        )

    def to_record(self) -> dict[str, object]:
        return asdict(self)
