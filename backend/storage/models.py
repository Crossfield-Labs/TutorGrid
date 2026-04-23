from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from backend.sessions.state import OrchestratorSessionState


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


def build_message_rows(session: OrchestratorSessionState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(list(session.context.get("planner_messages") or []), start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "session_id": session.session_id,
                "seq": index,
                "role": str(item.get("role") or "user"),
                "message_type": _detect_message_type(item),
                "content_text": str(item.get("content") or ""),
                "content_json": item,
                "tool_name": str(item.get("name") or ""),
                "tool_call_id": str(item.get("tool_call_id") or ""),
                "created_at": session.updated_at,
            }
        )
    return rows


def build_error_rows(session: OrchestratorSessionState) -> list[dict[str, Any]]:
    error_text = str(session.error or "").strip()
    if not error_text:
        return []
    return [
        {
            "session_id": session.session_id,
            "seq": 1,
            "error_layer": "runtime",
            "error_code": session.stop_reason or "runtime_error",
            "message": error_text,
            "details_json": {
                "phase": session.phase,
                "runner": session.runner,
                "activeWorker": session.active_worker,
            },
            "retryable": session.stop_reason not in {"cancelled"},
            "phase": session.phase,
            "worker": session.active_worker,
            "created_at": session.updated_at,
        }
    ]


def build_artifact_rows(session: OrchestratorSessionState) -> list[dict[str, Any]]:
    artifact_map: dict[str, dict[str, Any]] = {}
    for path in list(session.artifacts):
        artifact_map[str(path)] = {
            "session_id": session.session_id,
            "path": str(path),
            "change_type": "unknown",
            "size": None,
            "summary": session.latest_artifact_summary,
            "created_at": session.updated_at,
        }

    for run in list(session.worker_runs or []):
        for artifact in list(run.get("artifacts") or []):
            if not isinstance(artifact, dict):
                continue
            path = str(artifact.get("path") or "").strip()
            if not path:
                continue
            artifact_map[path] = {
                "session_id": session.session_id,
                "path": path,
                "change_type": str(artifact.get("change_type") or "unknown"),
                "size": artifact.get("size"),
                "summary": session.latest_artifact_summary,
                "created_at": session.updated_at,
            }
    return list(artifact_map.values())


def _detect_message_type(item: dict[str, Any]) -> str:
    if item.get("tool_calls"):
        return "tool_call"
    if str(item.get("role") or "").lower() == "tool":
        return "tool_result"
    if str(item.get("role") or "").lower() == "system":
        return "system"
    return "message"

