from __future__ import annotations

from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def finalize_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    next_state["phase"] = "completed"
    next_state["status"] = "COMPLETED"
    next_state["last_progress_message"] = "Runtime graph completed."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=1.0,
    )
    return next_state
