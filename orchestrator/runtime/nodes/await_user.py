from __future__ import annotations

from orchestrator.runtime.state import RuntimeState


def await_user_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    next_state["phase"] = "awaiting_user"
    next_state["awaiting_input"] = True
    next_state["pending_user_prompt"] = "User input is required."
    next_state["last_progress_message"] = "Graph is waiting for user input."
    return next_state
