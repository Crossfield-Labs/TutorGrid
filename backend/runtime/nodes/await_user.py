from __future__ import annotations

from typing import Any

from backend.llm.messages import append_user_message
from backend.runtime.context_registry import resolve_runtime_context
from backend.runtime.session_sync import sync_session_from_runtime_state
from backend.runtime.state import RuntimeState

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover
    interrupt = None


async def await_user_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = resolve_runtime_context(next_state)
    session = runtime_context.get("session")
    prompt = str(next_state.get("pending_user_prompt") or (session.pending_user_prompt if session is not None else "") or "User input is required.")
    input_mode = str((session.context.get("pending_user_input_mode") if session is not None else "") or "text")
    next_state["phase"] = "awaiting_user"
    next_state["awaiting_input"] = True
    next_state["pending_user_prompt"] = prompt
    next_state["followups"] = list(session.followups) if session is not None else list(next_state.get("followups") or [])
    next_state["last_progress_message"] = "Graph is waiting for user input."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.55,
    )

    if interrupt is None:
        return next_state

    payload = interrupt(
        {
            "prompt": prompt,
            "input_mode": input_mode,
            "resume_method": "orchestrator.task.resume",
        }
    )
    reply_text = _coerce_resume_text(payload)

    next_state["awaiting_input"] = False
    next_state["pending_user_prompt"] = ""
    next_state["phase"] = "planning"
    next_state["last_progress_message"] = "已收到补充输入，继续执行。"
    next_state["messages"] = append_user_message(
        list(next_state.get("messages") or []),
        content=f"The user replied to the pending question:\n{reply_text}",
    )
    tool_events = list(next_state.get("tool_events") or [])
    tool_events.append({"tool": "await_user", "result": reply_text})
    next_state["tool_events"] = tool_events
    if session is not None:
        session.resume_with_input(reply_text)
        session.context.pop("pending_user_input_mode", None)
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.62,
    )
    return next_state


def _coerce_resume_text(payload: Any) -> str:
    if isinstance(payload, dict):
        content = payload.get("content")
        if content is not None:
            return str(content)
        if payload.get("text") is not None:
            return str(payload.get("text"))
    if payload is None:
        return ""
    return str(payload)


