from __future__ import annotations

from typing import Any, TypedDict


class RuntimeState(TypedDict, total=False):
    session_id: str
    task_id: str
    node_id: str
    workspace: str
    task: str
    goal: str
    phase: str
    status: str
    latest_summary: str
    last_progress_message: str
    latest_artifact_summary: str
    active_worker: str
    active_session_mode: str
    active_worker_profile: str
    active_worker_task_id: str
    active_worker_can_interrupt: bool
    awaiting_input: bool
    pending_user_prompt: str
    stop_reason: str
    followups: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    planned_tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    artifacts: list[str]
    worker_runs: list[dict[str, Any]]
    worker_sessions: dict[str, dict[str, Any]]
    substeps: list[dict[str, Any]]
    final_answer: str
    error: str
    iteration: int
    max_iterations: int

def create_initial_state(
    *,
    session_id: str,
    task_id: str,
    node_id: str,
    workspace: str,
    task: str,
    goal: str,
    max_iterations: int,
) -> RuntimeState:
    return RuntimeState(
        session_id=session_id,
        task_id=task_id,
        node_id=node_id,
        workspace=workspace,
        task=task,
        goal=goal or task,
        phase="created",
        status="PENDING",
        latest_summary="",
        last_progress_message="",
        latest_artifact_summary="",
        active_worker="",
        active_session_mode="",
        active_worker_profile="",
        active_worker_task_id="",
        active_worker_can_interrupt=False,
        awaiting_input=False,
        pending_user_prompt="",
        stop_reason="",
        followups=[],
        messages=[],
        planned_tool_calls=[],
        tool_results=[],
        tool_events=[],
        artifacts=[],
        worker_runs=[],
        worker_sessions={},
        substeps=[],
        final_answer="",
        error="",
        iteration=0,
        max_iterations=max_iterations,
    )

