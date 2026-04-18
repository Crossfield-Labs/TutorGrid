from __future__ import annotations

from orchestrator.runtime.state import RuntimeState


def planning_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    planner = dict(next_state.get("context") or {}).get("planner")
    iteration = int(next_state.get("iteration") or 0) + 1
    next_state["iteration"] = iteration
    next_state["phase"] = "planning"
    next_state["status"] = "RUNNING"
    next_state["messages"] = planner.build_messages(
        task=str(next_state.get("task") or ""),
        goal=str(next_state.get("goal") or ""),
        history=list(next_state.get("messages") or []),
    )
    next_state["last_progress_message"] = f"Planning iteration {iteration} with LangGraph and LangChain"
    if iteration >= 2:
        next_state["final_answer"] = "Standalone orchestrator runtime bootstrap completed."
        next_state["latest_summary"] = next_state["final_answer"]
    return next_state
