from __future__ import annotations

import json

from orchestrator.llm.messages import append_assistant_message
from orchestrator.runtime.session_sync import sync_session_from_runtime_state
from orchestrator.runtime.state import RuntimeState


async def planning_node(state: RuntimeState) -> RuntimeState:
    next_state = RuntimeState(**dict(state))
    runtime_context = dict(next_state.get("context") or {})
    planner = runtime_context.get("planner")
    tool_definitions = list(runtime_context.get("tool_definitions") or [])
    session = runtime_context.get("session")
    iteration = int(next_state.get("iteration") or 0) + 1
    next_state["iteration"] = iteration
    next_state["phase"] = "planning"
    next_state["status"] = "RUNNING"
    task = str(next_state.get("task") or "").strip()
    goal = str(next_state.get("goal") or task).strip()
    workspace = str(next_state.get("workspace") or ".")
    max_iterations = int(next_state.get("max_iterations") or 8)
    tool_results = list(next_state.get("tool_results") or [])
    history = list(next_state.get("messages") or [])

    if session is not None:
        consumed_followups: list[dict[str, str]] = []
        while session.followups:
            consumed_followups.append(session.followups.pop(0))
        for followup in consumed_followups:
            intent = str(followup.get("intent") or "comment").strip().lower() or "comment"
            text = str(followup.get("text") or "").strip()
            target = str(followup.get("target") or "").strip()
            if not text:
                continue
            if intent == "redirect":
                content = (
                    "The user changed direction for the current task.\n"
                    "Treat this as a high-priority update and revise the plan without losing state.\n"
                    f"Direction change: {text}"
                )
            else:
                content = (
                    "The user sent a follow-up message for the current task.\n"
                    "Use it as additional context while continuing the same task.\n"
                    f"Follow-up: {text}"
                )
            if target:
                content += f"\nTarget: {target}"
            history.append({"role": "user", "content": content})

    messages, response = await planner.plan(
        task=task,
        goal=goal,
        history=history,
        tools=tool_definitions,
    )
    if response.tool_calls:
        assistant_tool_calls = [
            {
                "id": item.id,
                "type": "function",
                "function": {
                    "name": item.name,
                    "arguments": json.dumps(item.arguments, ensure_ascii=False),
                },
            }
            for item in response.tool_calls
        ]
        next_state["messages"] = append_assistant_message(
            messages,
            content=response.content,
            tool_calls=assistant_tool_calls,
        )
        next_state["planned_tool_calls"] = [
            {"id": item.id, "tool": item.name, "arguments": item.arguments}
            for item in response.tool_calls
        ]
        next_state["last_progress_message"] = (
            f"Planning iteration {iteration} scheduled {len(response.tool_calls)} tool call(s)."
        )
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=min(0.08 + iteration * 0.06, 0.55),
        )
        return next_state

    if not tool_results and iteration < max(2, max_iterations):
        next_state["messages"] = append_assistant_message(messages, content=response.content)
        next_state["planned_tool_calls"] = [
            {"id": "bootstrap-list-files", "tool": "list_files", "arguments": {"path": str(next_state.get("workspace") or ".")}},
            {"id": "bootstrap-read-main", "tool": "read_file", "arguments": {"path": "main.py"}},
            {"id": "bootstrap-read-readme", "tool": "read_file", "arguments": {"path": "README.md"}},
        ]
        next_state["last_progress_message"] = (
            f"Planning iteration {iteration} produced no tool calls; scheduled bootstrap inspection tools."
        )
        next_state["latest_summary"] = str(response.content or "").strip()
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=min(0.08 + iteration * 0.06, 0.55),
        )
        return next_state

    if tool_results:
        forced_final = await planner.finalize_from_evidence(
            task=task,
            goal=goal,
            history=messages,
            evidence=tool_results,
            reason="Tool results are already available, so conclude from the collected evidence.",
        )
        if forced_final:
            next_state["messages"] = append_assistant_message(messages, content=forced_final)
            next_state["last_progress_message"] = f"Planning iteration {iteration} finalized from collected evidence."
            next_state["latest_summary"] = forced_final
            next_state["final_answer"] = forced_final
            await sync_session_from_runtime_state(
                next_state,
                emit_progress=runtime_context.get("emit_progress"),
                progress=0.9,
            )
            return next_state
        fallback = planner.build_fallback_summary(
            task=task,
            workspace=workspace,
            evidence=tool_results,
            reason="Planner did not return a final answer after evidence collection.",
        )
        next_state["messages"] = append_assistant_message(messages, content=fallback)
        next_state["last_progress_message"] = f"Planning iteration {iteration} used fallback evidence summary."
        next_state["latest_summary"] = fallback
        next_state["final_answer"] = fallback
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.9,
        )
        return next_state

    if iteration >= max_iterations:
        fallback = planner.build_fallback_summary(
            task=task,
            workspace=workspace,
            evidence=tool_results,
            reason=f"Reached max iterations ({max_iterations}) without a final answer.",
        )
        next_state["messages"] = append_assistant_message(messages, content=fallback)
        next_state["last_progress_message"] = f"Planning iteration {iteration} forced completion at max iterations."
        next_state["latest_summary"] = fallback
        next_state["final_answer"] = fallback
        await sync_session_from_runtime_state(
            next_state,
            emit_progress=runtime_context.get("emit_progress"),
            progress=0.9,
        )
        return next_state

    next_state["messages"] = append_assistant_message(messages, content=response.content)
    next_state["last_progress_message"] = f"Planning iteration {iteration} produced a final response."
    next_state["latest_summary"] = str(response.content or "").strip()
    next_state["final_answer"] = str(response.content or "").strip()
    await sync_session_from_runtime_state(
        next_state,
        emit_progress=runtime_context.get("emit_progress"),
        progress=0.9,
    )
    return next_state
