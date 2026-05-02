from __future__ import annotations

from backend.runtime.state import RuntimeState


def route_after_tools(state: RuntimeState) -> str:
    if state.get("final_answer"):
        return "finalize"
    if state.get("awaiting_input"):
        return "await_user"
    return "verify"


