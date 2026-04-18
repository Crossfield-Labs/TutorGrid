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
    awaiting_input: bool
    pending_user_prompt: str
    messages: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    artifacts: list[str]
    worker_runs: list[dict[str, Any]]
    final_answer: str
    error: str
    iteration: int
    max_iterations: int
    context: dict[str, Any]


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
        awaiting_input=False,
        pending_user_prompt="",
        messages=[],
        tool_results=[],
        artifacts=[],
        worker_runs=[],
        final_answer="",
        error="",
        iteration=0,
        max_iterations=max_iterations,
        context={},
    )
