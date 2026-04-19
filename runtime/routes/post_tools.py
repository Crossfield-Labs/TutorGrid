from __future__ import annotations

from runtime.state import RuntimeState


def route_after_tools(state: RuntimeState) -> str:
    if state.get("final_answer"):
        return "finalize"
    return "verify"

