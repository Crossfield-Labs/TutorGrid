from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from backend.sessions.state import OrchestratorSessionState
from backend.runtime.state import RuntimeState

ProgressCallback = Callable[[str, float | None], Awaitable[None]]
SubstepCallback = Callable[[str, str, str, str | None], Awaitable[None]]
MessageEventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]
DocWriteCallback = Callable[[dict[str, Any]], Awaitable[None]]
PlanCallback = Callable[[dict[str, Any]], Awaitable[None]]


class RuntimeExecutionContext(TypedDict, total=False):
    planner: Any
    tools: list[Any]
    tool_map: dict[str, Any]
    tool_definitions: list[dict[str, Any]]
    session: OrchestratorSessionState
    emit_progress: ProgressCallback | None
    emit_substep: SubstepCallback | None
    emit_message_event: MessageEventCallback | None
    emit_doc_write: DocWriteCallback | None
    emit_plan: PlanCallback | None
    memory_service: Any
    memory_config: Any
    tracer: Any
    langsmith_parent_run_id: str


_CONTEXTS: dict[str, RuntimeExecutionContext] = {}


def register_runtime_context(session_id: str, context: RuntimeExecutionContext) -> None:
    if not session_id:
        return
    _CONTEXTS[session_id] = context


def get_runtime_context(session_id: str) -> RuntimeExecutionContext:
    return dict(_CONTEXTS.get(session_id) or {})


def resolve_runtime_context(state: RuntimeState) -> RuntimeExecutionContext:
    session_id = str(state.get("session_id") or "")
    if session_id and session_id in _CONTEXTS:
        return dict(_CONTEXTS[session_id])
    legacy_context = state.get("context") if isinstance(state, dict) else None
    if isinstance(legacy_context, dict):
        return dict(legacy_context)
    return {}


def unregister_runtime_context(session_id: str) -> None:
    if not session_id:
        return
    _CONTEXTS.pop(session_id, None)
