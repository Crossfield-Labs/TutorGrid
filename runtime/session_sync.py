from __future__ import annotations

from typing import Awaitable, Callable

from runtime.state import RuntimeState

ProgressCallback = Callable[[str, float | None], Awaitable[None]]


async def sync_session_from_runtime_state(
    state: RuntimeState,
    *,
    emit_progress: ProgressCallback | None = None,
    progress: float | None = None,
) -> RuntimeState:
    context = dict(state.get("context") or {})
    session = context.get("session")
    if session is None:
        return state

    if "phase" in state:
        session.phase = str(state.get("phase") or session.phase)
    if "status" in state:
        session.status = str(state.get("status") or session.status)
    if "latest_summary" in state:
        session.latest_summary = str(state.get("latest_summary") or "")
    if "last_progress_message" in state:
        session.last_progress_message = str(state.get("last_progress_message") or "")
    if "latest_artifact_summary" in state:
        session.latest_artifact_summary = str(state.get("latest_artifact_summary") or "")
    if "active_worker" in state:
        session.active_worker = str(state.get("active_worker") or "")
    if "active_session_mode" in state:
        session.active_session_mode = str(state.get("active_session_mode") or "")
    if "active_worker_profile" in state:
        session.active_worker_profile = str(state.get("active_worker_profile") or "")
    if "active_worker_task_id" in state:
        session.active_worker_task_id = str(state.get("active_worker_task_id") or "")
    if "active_worker_can_interrupt" in state:
        session.active_worker_can_interrupt = bool(state.get("active_worker_can_interrupt") or False)
    if "awaiting_input" in state:
        session.awaiting_input = bool(state.get("awaiting_input") or False)
    if "pending_user_prompt" in state:
        session.pending_user_prompt = str(state.get("pending_user_prompt") or "")
    if "stop_reason" in state:
        session.stop_reason = str(state.get("stop_reason") or "")
    if "followups" in state:
        session.followups = list(state.get("followups") or [])
    if "artifacts" in state:
        session.artifacts = list(state.get("artifacts") or [])
    if "worker_runs" in state:
        session.worker_runs = list(state.get("worker_runs") or [])
    if "worker_sessions" in state:
        session.worker_sessions = dict(state.get("worker_sessions") or {})
    if "substeps" in state:
        session.substeps = list(state.get("substeps") or [])
    if "final_answer" in state:
        session.result = str(state.get("final_answer") or "")
    if "error" in state:
        session.error = str(state.get("error") or "")
    if "messages" in state:
        session.context["planner_messages"] = list(state.get("messages") or [])
    if "tool_events" in state:
        session.context["tool_events"] = list(state.get("tool_events") or [])

    if emit_progress is not None and state.get("last_progress_message"):
        await emit_progress(str(state.get("last_progress_message") or ""), progress)
    return state

