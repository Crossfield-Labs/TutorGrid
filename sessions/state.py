from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class OrchestratorSessionState:
    task_id: str
    node_id: str
    runner: str
    workspace: str
    task: str
    goal: str
    session_id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "PENDING"
    phase: str = "created"
    result: str = ""
    error: str = ""
    stop_reason: str = ""
    latest_summary: str = ""
    last_progress_message: str = ""
    latest_artifact_summary: str = ""
    permission_summary: str = ""
    session_info_summary: str = ""
    mcp_status_summary: str = ""
    input_mode: str = "text"
    active_worker: str = ""
    active_session_mode: str = ""
    active_worker_profile: str = ""
    active_worker_task_id: str = ""
    active_worker_can_interrupt: bool = False
    pending_user_prompt: str = ""
    awaiting_input: bool = False
    artifacts: list[str] = field(default_factory=list)
    worker_runs: list[dict[str, Any]] = field(default_factory=list)
    worker_sessions: dict[str, Any] = field(default_factory=dict)
    substeps: list[dict[str, Any]] = field(default_factory=list)
    followups: list[dict[str, Any]] = field(default_factory=list)
    hook_events: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    snapshot_version: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.snapshot_version += 1

    def mark(self, *, status: str, message: str) -> None:
        self.status = status
        self.last_progress_message = message
        self.touch()

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.touch()

    def set_latest_summary(self, summary: str) -> None:
        self.latest_summary = summary
        self.touch()

    def set_stop_reason(self, reason: str) -> None:
        self.stop_reason = reason
        self.touch()

    def set_latest_artifact_summary(self, summary: str) -> None:
        self.latest_artifact_summary = summary
        self.touch()

    def set_permission_summary(self, summary: str) -> None:
        self.permission_summary = summary
        self.touch()

    def set_session_info_summary(self, summary: str) -> None:
        self.session_info_summary = summary
        self.touch()

    def set_mcp_status_summary(self, summary: str) -> None:
        self.mcp_status_summary = summary
        self.touch()

    def set_active_worker_runtime(
        self,
        *,
        worker: str,
        session_mode: str,
        task_id: str,
        profile: str,
        can_interrupt: bool = False,
    ) -> None:
        self.active_worker = worker
        self.active_session_mode = session_mode
        self.active_worker_task_id = task_id
        self.active_worker_profile = profile
        self.active_worker_can_interrupt = can_interrupt
        self.touch()

    def request_user_input(self, message: str, input_mode: str) -> None:
        self.awaiting_input = True
        self.pending_user_prompt = message
        self.input_mode = input_mode
        self.touch()

    def resume_with_input(self, text: str) -> None:
        self.awaiting_input = False
        self.pending_user_prompt = ""
        self.context["last_user_input"] = text
        self.touch()

    def add_hook_event(self, **event: Any) -> None:
        self.hook_events.append(event)
        self.touch()

    def drain_followups(self) -> list[dict[str, Any]]:
        items = list(self.followups)
        self.followups.clear()
        self.touch()
        return items

    def build_snapshot(self) -> dict[str, Any]:
        return {
            "snapshotVersion": self.snapshot_version,
            "status": self.status,
            "phase": self.phase,
            "activeWorker": self.active_worker,
            "activeSessionMode": self.active_session_mode,
            "activeWorkerProfile": self.active_worker_profile,
            "activeWorkerTaskId": self.active_worker_task_id,
            "activeWorkerCanInterrupt": self.active_worker_can_interrupt,
            "latestSummary": self.latest_summary,
            "lastProgressMessage": self.last_progress_message,
            "latestArtifactSummary": self.latest_artifact_summary,
            "permissionSummary": self.permission_summary,
            "sessionInfoSummary": self.session_info_summary,
            "mcpStatusSummary": self.mcp_status_summary,
            "awaitingInput": self.awaiting_input,
            "pendingUserPrompt": self.pending_user_prompt,
            "pendingFollowups": list(self.followups),
            "artifacts": list(self.artifacts),
            "recentHookEvents": list(self.hook_events[-10:]),
        }
