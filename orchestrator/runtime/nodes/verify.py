from __future__ import annotations

from orchestrator.runtime.state import RuntimeState


def verify_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    next_state["phase"] = "verifying"
    next_state["last_progress_message"] = "Verifying intermediate runtime state."
    return next_state
