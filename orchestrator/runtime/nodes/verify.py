from __future__ import annotations

from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def verify_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    next_state["phase"] = "verifying"
    if next_state.get("final_answer"):
        next_state["last_progress_message"] = "Verification passed with a final answer present."
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.92,
        )
        return next_state

    next_state["last_progress_message"] = "Verification completed; returning to planning with collected evidence."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.78,
    )
    return next_state
