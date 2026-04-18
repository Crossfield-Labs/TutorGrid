from __future__ import annotations

import asyncio
from typing import Any

from orchestrator.llm.messages import append_tool_message
from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def tools_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    tool_map = dict(runtime_context.get("tool_map") or {})
    emit_substep = runtime_context.get("emit_substep")
    session = runtime_context.get("session")
    planned_calls = list(next_state.get("planned_tool_calls") or [])
    executed_results = list(next_state.get("tool_results") or [])
    tool_events = list(next_state.get("tool_events") or [])
    messages = list(next_state.get("messages") or [])
    substeps = list(next_state.get("substeps") or [])

    for call in planned_calls:
        tool_name = str(call.get("tool") or "").strip()
        arguments = dict(call.get("arguments") or {})
        tool = tool_map.get(tool_name)
        phase = _phase_for_tool(tool_name)
        next_state["phase"] = phase
        if tool is None:
            if emit_substep is not None:
                await emit_substep("tool", tool_name, "failed", f"Tool '{tool_name}' is not registered.")
            substeps.append({"kind": "tool", "title": tool_name, "status": "failed", "detail": f"Tool '{tool_name}' is not registered."})
            executed_results.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": f"Error: tool '{tool_name}' is not registered.",
                }
            )
            tool_events.append({"tool": tool_name, "arguments": arguments, "result": f"Error: tool '{tool_name}' is not registered."})
            continue

        if emit_substep is not None:
            await emit_substep("tool", tool_name, "started", f"Executing {tool_name}")
        substeps.append({"kind": "tool", "title": tool_name, "status": "started", "detail": f"Executing {tool_name}"})
        if hasattr(tool, "ainvoke"):
            result = await tool.ainvoke(arguments)
        else:
            result = tool.invoke(arguments)
            if asyncio.iscoroutine(result):
                result = await result
        executed_results.append(
            {
                "id": str(call.get("id") or ""),
                "tool": tool_name,
                "arguments": arguments,
                "result": str(result),
            }
        )
        tool_events.append({"tool": tool_name, "arguments": arguments, "result": str(result)})
        messages = append_tool_message(
            messages,
            tool_call_id=str(call.get("id") or tool_name),
            tool_name=tool_name,
            result=str(result),
        )
        if emit_substep is not None:
            await emit_substep("tool", tool_name, "completed", str(result)[:240])
        substeps.append({"kind": "tool", "title": tool_name, "status": "completed", "detail": str(result)[:240]})

    if not planned_calls:
        next_state["phase"] = "planning"
    next_state["messages"] = messages
    next_state["tool_results"] = executed_results
    next_state["tool_events"] = tool_events
    next_state["substeps"] = substeps
    next_state["planned_tool_calls"] = []
    if session is not None:
        next_state["followups"] = list(session.followups)
        next_state["artifacts"] = list(session.artifacts)
        next_state["worker_runs"] = list(session.worker_runs)
        next_state["worker_sessions"] = dict(session.worker_sessions)
        next_state["active_worker"] = str(session.active_worker or "")
        next_state["active_session_mode"] = str(session.active_session_mode or "")
        next_state["active_worker_profile"] = str(session.active_worker_profile or "")
        next_state["active_worker_task_id"] = str(session.active_worker_task_id or "")
        next_state["active_worker_can_interrupt"] = bool(session.active_worker_can_interrupt)
        next_state["latest_artifact_summary"] = str(session.latest_artifact_summary or "")
    next_state["last_progress_message"] = f"Executed {len(planned_calls)} tool call(s)."
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.72,
    )
    return next_state


def _phase_for_tool(tool_name: str) -> str:
    if tool_name in {"delegate_task", "delegate_opencode"}:
        return "delegating"
    if tool_name == "await_user":
        return "awaiting_user"
    if tool_name == "run_shell":
        return "verifying"
    if tool_name in {"list_files", "read_file", "web_fetch"}:
        return "inspecting"
    return "planning"
