from __future__ import annotations

from backend.runtime.session_sync import sync_session_from_runtime_state
from backend.runtime.state import RuntimeState


async def await_user_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    session = runtime_context.get("session")
    if session is not None and session.awaiting_input:
        next_state["phase"] = "awaiting_user"
        next_state["awaiting_input"] = True
        next_state["pending_user_prompt"] = str(session.pending_user_prompt or "User input is required.")
        next_state["followups"] = list(session.followups)
        next_state["last_progress_message"] = "Graph is waiting for user input."
    else:
        next_state["awaiting_input"] = False
        next_state["pending_user_prompt"] = ""
        next_state["phase"] = "planning"
        next_state["last_progress_message"] = "Await-user node resumed after receiving user input."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.55,
    )
    return next_state


