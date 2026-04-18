from __future__ import annotations

from orchestrator.runtime.state import RuntimeState


def finalize_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    next_state["phase"] = "completed"
    next_state["status"] = "COMPLETED"
    next_state["last_progress_message"] = "Runtime graph completed."
    return next_state
