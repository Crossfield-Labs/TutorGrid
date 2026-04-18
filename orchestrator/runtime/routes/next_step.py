from __future__ import annotations

from orchestrator.runtime.state import RuntimeState


def route_after_planning(state: RuntimeState) -> str:
    if state.get("final_answer"):
        return "finalize"
    if state.get("planned_tool_calls"):
        return "tools"
    if state.get("awaiting_input"):
        return "await_user"
    return "verify"
