from __future__ import annotations

from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def verify_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    planner = runtime_context.get("planner")
    next_state["phase"] = "verifying"
    if next_state.get("final_answer"):
        next_state["last_progress_message"] = "Verification passed with a final answer present."
        next_state["stop_reason"] = str(next_state.get("stop_reason") or "completed")
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.92,
        )
        return next_state

    iteration = int(next_state.get("iteration") or 0)
    max_iterations = int(next_state.get("max_iterations") or 8)
    if iteration >= max_iterations:
        fallback = planner.build_fallback_summary(
            task=str(next_state.get("task") or ""),
            workspace=str(next_state.get("workspace") or "."),
            evidence=list(next_state.get("tool_results") or []),
            reason=f"Reached max iterations ({max_iterations}) during verification.",
        )
        next_state["latest_summary"] = fallback
        next_state["final_answer"] = fallback
        next_state["stop_reason"] = str(next_state.get("stop_reason") or "max_iterations_finalized")
        next_state["last_progress_message"] = "Verification forced completion at max iterations."
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
