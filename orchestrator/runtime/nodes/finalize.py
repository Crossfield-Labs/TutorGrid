from __future__ import annotations

from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def finalize_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    if not next_state.get("final_answer"):
        planner = runtime_context.get("planner")
        evidence = list(next_state.get("tool_results") or [])
        if planner is not None and evidence:
            next_state["final_answer"] = planner.build_fallback_summary(
                task=str(next_state.get("task") or ""),
                workspace=str(next_state.get("workspace") or "."),
                evidence=evidence,
                reason="Finalized directly from collected tool evidence.",
            )
        else:
            next_state["final_answer"] = str(
                next_state.get("latest_summary")
                or next_state.get("last_progress_message")
                or "Runtime graph completed."
            )
    next_state["phase"] = "completed"
    next_state["status"] = "COMPLETED"
    next_state["stop_reason"] = str(next_state.get("stop_reason") or "completed")
    next_state["last_progress_message"] = "Runtime graph completed."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=1.0,
    )
    return next_state
